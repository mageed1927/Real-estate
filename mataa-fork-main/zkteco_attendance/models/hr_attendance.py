from odoo import models, fields, api
from datetime import timedelta
from odoo.exceptions import UserError

class HrAttendance(models.Model):
    _inherit = 'hr.attendance'

    plus_hours = fields.Char(string="Plus Hours", compute='_compute_plus_negative', store=True)
    negative_hours = fields.Char(string="Negative Hours", compute='_compute_plus_negative', store=True)
    early_in = fields.Char(string="Early In", compute='_compute_plus_negative', store=True)
    early_out = fields.Char(string="Early Out", compute='_compute_plus_negative', store=True)
    late_in = fields.Char(string="Late In", compute='_compute_plus_negative', store=True)
    late_out = fields.Char(string="Late Out", compute='_compute_plus_negative', store=True)
    is_time_off = fields.Boolean(string="Is Time Off", help="Tick if this absence is justified as paid time off.", store=True, tracking=True)
    is_fallback_checkout = fields.Boolean("Used Fallback Check-Out", default=False)

    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            if rec.employee_id.time_off_balance < 1 and rec.is_time_off:
                raise UserError(
                    "This action will make the employee's time off balance negative!\n"
                    "Please increase the balance or consult HR."
                )
            if 'is_time_off' in vals and vals['is_time_off'] and rec.worked_hours < 1:
                leave_obj = self.env['hr.leave']
                check_in_date = rec.check_in.date()
                existing_leave = leave_obj.search([
                    ('employee_id', '=', rec.employee_id.id),
                    ('request_date_from', '<=', check_in_date),
                    ('request_date_to', '>=', check_in_date),
                    ('state', 'in', ['draft', 'confirm', 'validate', 'refuse']),
                ], limit=1)

                if not existing_leave:

                    leave_type = self.env.ref('hr_holidays.holiday_status_cl', raise_if_not_found=False)
                    if not leave_type:
                        raise UserError(
                            'Paid Time Off leave type not found. Please set up a leave type and update the external_id in code.')

                    leave = leave_obj.create({
                        'employee_id': rec.employee_id.id,
                        'holiday_status_id': leave_type.id,
                        'request_date_from': check_in_date,
                        'request_date_to': check_in_date,
                        'number_of_days': 1,
                        'name': 'Auto Created Paid Time Off (from attendance)',
                    })
                    # TODO: Uncomment if we want to approve leave once it's created
                    #leave.action_approve()
                rec.employee_id.time_off_balance -= 1
        return res

    @api.depends('check_in', 'check_out', 'employee_id')
    def _compute_plus_negative(self):
        for rec in self:
            rec.plus_hours = "00:00:00"
            rec.negative_hours = "00:00:00"
            rec.early_in = "00:00:00"
            rec.early_out = "00:00:00"
            rec.late_in = "00:00:00"
            rec.late_out = "00:00:00"

            if not rec.check_in or not rec.check_out or not rec.employee_id.resource_calendar_id:
                continue

            # Ignore days with 00:00 worked hours
            worked_hours = (rec.check_out - rec.check_in).total_seconds() / 3600.0
            if worked_hours < 1:
                continue

            # Get the calendar and attendance lines for the employee
            calendar = rec.employee_id.resource_calendar_id
            local_check_in = fields.Datetime.context_timestamp(rec, rec.check_in)
            local_check_out = fields.Datetime.context_timestamp(rec, rec.check_out)
            weekday = str(local_check_in.weekday())
            attendance_lines = calendar.attendance_ids.filtered(lambda a: a.dayofweek == weekday)

            if not attendance_lines:
                worked_time = rec.check_out - rec.check_in
                rec.plus_hours = str(worked_time).split('.')[0]
                rec.negative_hours = "00:00:00"
                continue

            # Early/Late In
            early_in_delta = None
            late_in_delta = None
            for att in attendance_lines:
                shift_start = local_check_in.replace(
                    hour=int(att.hour_from),
                    minute=int((att.hour_from % 1) * 60),
                    second=0, microsecond=0
                )
                if local_check_in < shift_start:
                    delta = shift_start - local_check_in
                    if early_in_delta is None or delta < early_in_delta:
                        early_in_delta = delta
                elif local_check_in > shift_start:
                    delta = local_check_in - shift_start
                    if late_in_delta is None or delta < late_in_delta:
                        late_in_delta = delta
            if early_in_delta:
                rec.early_in = str(early_in_delta).split('.')[0]
            if late_in_delta:
                rec.late_in = str(late_in_delta).split('.')[0]

            # Early/Late Out
            early_out_delta = None
            late_out_delta = None
            for att in attendance_lines:
                shift_end = local_check_in.replace(
                    hour=int(att.hour_to),
                    minute=int((att.hour_to % 1) * 60),
                    second=0, microsecond=0
                )
                if att.hour_to < att.hour_from:
                    shift_end += timedelta(days=1)
                if local_check_out < shift_end:
                    delta = shift_end - local_check_out
                    if early_out_delta is None or delta > early_out_delta:
                        early_out_delta = delta
                elif local_check_out > shift_end:
                    delta = local_check_out - shift_end
                    if late_out_delta is None or delta > late_out_delta:
                        late_out_delta = delta
            if early_out_delta:
                rec.early_out = str(early_out_delta).split('.')[0]
            if late_out_delta:
                rec.late_out = str(late_out_delta).split('.')[0]

            # Calculate Plus and Negative Hours
            avg_working_hours = rec.employee_id.resource_calendar_id.hours_per_day or 0.0
            if worked_hours > avg_working_hours:
                plus = timedelta(hours=worked_hours - avg_working_hours)
                rec.plus_hours = str(plus).split('.')[0]
                rec.negative_hours = "00:00:00"
            elif worked_hours < avg_working_hours:
                negative = timedelta(hours=avg_working_hours - worked_hours)
                rec.negative_hours = str(negative).split('.')[0]
                rec.plus_hours = "00:00:00"
            else:
                rec.plus_hours = "00:00:00"
                rec.negative_hours = "00:00:00"

    def action_open_zkteco_fetch_wizard(self):
        return {
            'name': 'جلب بصمات ZKTeco',
            'type': 'ir.actions.act_window',
            'res_model': 'ztkeco.fetch.wizard',
            'view_mode': 'form',
            'target': 'new',
        }

    def action_process_zkteco_punches(self):
        result = self.env['ztkeco.punch'].process_zkteco_punches()
        errors = result.get('errors') or []
        message = result.get('message', 'تمت المعالجة.')
        if errors:
            message = '\n'.join([message] + errors[:40])
            if len(errors) > 40:
                message += '\n…'
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'ZKTeco',
                'message': message,
                'sticky': bool(errors),
                'type': 'warning' if errors else 'success',
            },
        }