from odoo import models, fields, api
from datetime import datetime, timedelta
import logging
_logger = logging.getLogger(__name__)

class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    custom_hours_per_day = fields.Float(
        string="Custom Hours/Day",
        help="Optional override for working hours per day."
    )
    attendance_count = fields.Integer(compute='_compute_attendance_count', string="Attendances")

    def _compute_attendance_count(self):
        for rec in self:
            rec.attendance_count = self.env['hr.attendance'].search_count([
                ('employee_id', '=', rec.employee_id.id),
                ('check_in', '>=', rec.date_from),
                ('check_out', '<=', rec.date_to),
            ])

    def action_open_attendances(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Attendances',
            'res_model': 'hr.attendance',
            'view_mode': 'tree,form',
            'domain': [
                ('employee_id', '=', self.employee_id.id),
                ('check_in', '>=', self.date_from),
                ('check_out', '<=', self.date_to),
            ],
            'context': {
                'default_employee_id': self.employee_id.id,
            }
        }


class HrPayslipWorkedDays(models.Model):
    _inherit = 'hr.payslip.worked_days'

    plus_hours = fields.Char(string="Plus", compute='_compute_net_amount', store=True)
    negative_hours = fields.Char(string="Negative", compute='_compute_net_amount', store=True)
    net_amount = fields.Float(string='Net Amount', compute='_compute_net_amount', store=True)
    total_early_in = fields.Char(string="Early In", compute='_compute_net_amount', store=True)
    total_early_out = fields.Char(string="Early Out", compute='_compute_net_amount', store=True)
    total_late_in = fields.Char(string="Late In", compute='_compute_net_amount', store=True)
    total_late_out = fields.Char(string="Late Out", compute='_compute_net_amount', store=True)
    absence_days = fields.Integer(string="Absence Days", compute='_compute_absence_days',store=True)
    plus_amount = fields.Float(string="Assignment of Salary", compute='_compute_net_amount', store=True)
    minus_amount = fields.Float(string="Deduction", compute='_compute_net_amount', store=True)

    @api.depends('number_of_hours', 'payslip_id.contract_id.wage', 'payslip_id.date_from', 'payslip_id.date_to','payslip_id.custom_hours_per_day', 'absence_days')
    def _compute_net_amount(self):
        def parse_time_string(time_str):
            try:
                h, m, s = map(int, time_str.split(':'))
                return timedelta(hours=h, minutes=m, seconds=s)
            except Exception:
                return timedelta()

        # Function to format timedelta into HH:MM:SS string
        def format_timedelta(td):
            total_seconds = int(td.total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60
            return f"{hours:02}:{minutes:02}:{seconds:02}"

        # Ensure we only compute for records that are part of the current payslip
        for rec in self:
            contract = rec.payslip_id.contract_id
            employee = rec.payslip_id.employee_id

            if not contract or not employee:
                rec.net_amount = 0.0
                rec.plus_hours = "00:00:00"
                rec.negative_hours = "00:00:00"
                rec.total_early_in = "00:00:00"
                rec.total_early_out = "00:00:00"
                rec.total_late_in = "00:00:00"
                rec.total_late_out = "00:00:00"
                continue

            attendance_records = self.env['hr.attendance'].search([
                ('employee_id', '=', employee.id),
                ('check_in', '>=', rec.payslip_id.date_from),
                ('check_out', '<=', rec.payslip_id.date_to)
            ])

            # calculate total early/late in/out times
            total_early_in_td = sum((parse_time_string(a.early_in) for a in attendance_records), timedelta())
            total_early_out_td = sum((parse_time_string(a.early_out) for a in attendance_records), timedelta())
            total_late_in_td = sum((parse_time_string(a.late_in) for a in attendance_records), timedelta())
            total_late_out_td = sum((parse_time_string(a.late_out) for a in attendance_records), timedelta())


            rec.total_early_in = format_timedelta(total_early_in_td)
            rec.total_early_out = format_timedelta(total_early_out_td)
            rec.total_late_in = format_timedelta(total_late_in_td)
            rec.total_late_out = format_timedelta(total_late_out_td)

            total_plus_td = sum((parse_time_string(a.plus_hours or "00:00:00") for a in attendance_records), timedelta())
            total_negative_td = sum((parse_time_string(a.negative_hours or "00:00:00") for a in attendance_records), timedelta())

            total_plus_hours = total_plus_td.total_seconds() / 3600
            total_negative_hours = total_negative_td.total_seconds() / 3600

            rec.plus_hours = format_timedelta(total_plus_td)
            rec.negative_hours = format_timedelta(total_negative_td)

            calendar = contract.resource_calendar_id
            hours_per_day = rec.payslip_id.custom_hours_per_day or (calendar.hours_per_day if calendar else 8)
            monthly_salary = contract.wage

            plus_amount = (monthly_salary / 26 / hours_per_day) * total_plus_hours
            minus_amount = (monthly_salary / 30 / hours_per_day) * total_negative_hours

            rec.plus_amount = plus_amount
            rec.minus_amount = minus_amount

            absence_deduction = (monthly_salary / 30) * rec.absence_days

            rec.net_amount = monthly_salary + plus_amount - minus_amount - absence_deduction

    @api.depends('payslip_id.employee_id', 'payslip_id.date_from', 'payslip_id.date_to','payslip_id.employee_id.attendance_ids.worked_hours', 'payslip_id.employee_id.attendance_ids.is_time_off')
    def _compute_absence_days(self):
        for rec in self:
            employee = rec.payslip_id.employee_id
            date_from = rec.payslip_id.date_from
            date_to = rec.payslip_id.date_to
            if employee and date_from and date_to:
                absence_count = self.env['hr.attendance'].search_count([
                    ('employee_id', '=', employee.id),
                    ('check_in', '>=', date_from),
                    ('check_out', '<=', date_to),
                    ('worked_hours', '<', 1),
                    ('is_time_off', '=', False),
                ])
                rec.absence_days = absence_count
            else:
                rec.absence_days = 0
