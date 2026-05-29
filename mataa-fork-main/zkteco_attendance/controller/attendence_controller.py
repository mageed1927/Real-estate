from itertools import groupby
from odoo import http
from odoo.http import request
import pytz
from types import SimpleNamespace

class EmployeeKiosk(http.Controller):

    def _sum_time_strings(self, time_strings):
        total_seconds = 0
        for time_str in time_strings:
            if not time_str or not isinstance(time_str, str):
                continue
            parts = time_str.split(':')
            try:
                h = int(parts[0])
                m = int(parts[1])
                s = int(parts[2])
                total_seconds += h * 3600 + m * 60 + s
            except (ValueError, IndexError):
                continue

        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}"

    @http.route('/employee_kiosk', type='http', auth='public', website=True)
    def employee_kiosk(self, **kwargs):
        search_query = kwargs.get('search', '')

        employees_domain = []
        if search_query:
            employees_domain = [('name', 'ilike', search_query)]

        employees = request.env['hr.employee'].sudo().search(employees_domain)
        return request.render('zkteco_attendance.kiosk_page', {
            'employees': employees,
            'search_query': search_query
        })

    @http.route('/employee_kiosk/login/<int:employee_id>', type='http', auth='public', website=True)
    def employee_pin_input(self, employee_id, **kwargs):
        employee = request.env['hr.employee'].sudo().browse(employee_id)
        if employee:
            return request.render('zkteco_attendance.employee_pin_input', {'employee': employee})
        return request.redirect('/employee_kiosk?error=invalid_employee')

    @http.route('/employee_kiosk/login', type='http', auth='public', methods=['POST'], website=True, csrf=False)
    def employee_kiosk_login(self, **post):
        pin = post.get('pin', '').strip()
        employee = request.env['hr.employee'].sudo().search([('pin', '=', pin)], limit=1)

        if employee:
            attendances = request.env['hr.attendance'].sudo().search([('employee_id', '=', employee.id)],
                                                                     order='check_in desc')

            employee_tz_str = employee.tz or 'UTC'
            local_tz = pytz.timezone(employee_tz_str)
            processed_records = []
            for att in attendances:
                local_check_in = None
                if att.check_in:
                    local_check_in = att.check_in.replace(tzinfo=pytz.utc).astimezone(local_tz).replace(tzinfo=None)

                local_check_out = None
                if att.check_out:
                    local_check_out = att.check_out.replace(tzinfo=pytz.utc).astimezone(local_tz).replace(tzinfo=None)

                processed_records.append(SimpleNamespace(
                    check_in=local_check_in,
                    check_out=local_check_out,
                    plus_hours=att.plus_hours,
                    negative_hours=att.negative_hours,
                    early_in=att.early_in,
                    early_out=att.early_out,
                    late_in=att.late_in,
                    late_out=att.late_out
                ))


            display_data = []

            for month_year, group in groupby(processed_records, key=lambda att: att.check_in.strftime('%Y-%m')):
                month_records = list(group)

                total_plus = self._sum_time_strings([rec.plus_hours for rec in month_records])
                total_negative = self._sum_time_strings([rec.negative_hours for rec in month_records])
                total_early_in = self._sum_time_strings([rec.early_in for rec in month_records])
                total_early_out = self._sum_time_strings([rec.early_out for rec in month_records])
                total_late_in = self._sum_time_strings([rec.late_in for rec in month_records])
                total_late_out = self._sum_time_strings([rec.late_out for rec in month_records])

                display_data.extend(month_records)

                display_data.append({
                    'is_total_row': True,
                    'month_name': month_records[0].check_in.strftime('%B %Y'),
                    'total_plus': total_plus,
                    'total_negative': total_negative,
                    'total_early_in': total_early_in,
                    'total_early_out': total_early_out,
                    'total_late_in': total_late_in,
                    'total_late_out': total_late_out,
                })

            return request.render('zkteco_attendance.employee_attendance', {
                'employee': employee,
                'attendance_data': display_data,
            })
        else:
            return request.redirect('/employee_kiosk?error=invalid_pin')