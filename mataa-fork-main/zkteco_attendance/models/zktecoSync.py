import requests
from odoo import models, fields, api
import logging
from datetime import datetime, timedelta, time
from collections import defaultdict
import pytz
from odoo.exceptions import ValidationError
from dateutil.relativedelta import relativedelta

_logger = logging.getLogger(__name__)


class ZKTecoPunch(models.Model):
    _name = 'ztkeco.punch'
    _description = "ZKTeco Punch Record"
    _order = 'punch_time desc'

    employee_id = fields.Many2one('hr.employee', string='Employee')
    punch_time = fields.Datetime(string='Punch Time')
    punch_state = fields.Selection([
        ('checkin', 'Check In'),
        ('checkout', 'Check Out')
    ], string='Punch State')
    state = fields.Selection([
        ('unprocessed', 'Unprocessed'),
        ('processed', 'Processed')
    ], default='unprocessed', string='Processing State')


class ZKTecoSync(models.Model):
    _name = 'ztkeco.sync'
    _description = "ZKTeco Attendance Sync"

    @api.model
    def fetch_zkteco_punches_date_range(self, date_from, date_to, employees):
        config = self.env['ir.config_parameter'].sudo()
        url = config.get_param('zkteco.url')
        username = config.get_param('zkteco.username')
        password = config.get_param('zkteco.password')

        if not url or not username or not password:
            return {
                'ok': False,
                'message': 'system parameters are not set correctly for ZKTeco.',
            }

        auth_response = requests.post(
            f"{url.rstrip('/')}/jwt-api-token-auth/",
            json={"username": username, "password": password},
            headers={"Content-Type": "application/json"}
        )

        if auth_response.status_code != 200:
            return {
                'ok': False,
                'message': 'failed to authenticate with ZKTeco.',
            }

        token = auth_response.json().get("token")
        headers = {
            "Authorization": f"JWT {token}",
            "Content-Type": "application/json"
        }

        attendance_url = f"{url.rstrip('/')}/iclock/api/transactions/?start_time={date_from} 00:00:00&end_time={date_to} 23:59:59"
        local_tz = pytz.timezone("Africa/Tripoli")

        error = False
        for employee in employees:
            page = 1
            while True:
                response = requests.get(attendance_url, headers=headers, params={
                    "emp_code": employee.ztkeco_id,
                    "page": page,
                    "page_size": 100
                })

                if response.status_code != 200:
                    error = True
                    _logger.warning(
                        "ZKTeco fetch failed (status=%s) for emp_code=%s page=%s: %s",
                        response.status_code,
                        employee.ztkeco_id,
                        page,
                        getattr(response, "text", ""),
                    )
                    break

                punches = response.json().get("data", [])
                if not punches:
                    break

                for entry in punches:
                    punch_time = entry.get("punch_time")
                    punch_state = entry.get("punch_state")

                    if not punch_time or punch_state is None:
                        error = True
                        continue

                    local_dt = local_tz.localize(datetime.strptime(punch_time, "%Y-%m-%d %H:%M:%S"))
                    utc_dt = local_dt.astimezone(pytz.utc).replace(tzinfo=None)

                    if utc_dt < datetime.now() - timedelta(days=365):
                        error = True
                        continue

                    punch_state_str = 'checkin' if str(punch_state) == '0' else 'checkout'

                    exists = self.env['ztkeco.punch'].search([
                        ('employee_id', '=', employee.id),
                        ('punch_time', '=', utc_dt)
                    ], limit=1)

                    if not exists:
                        self.env['ztkeco.punch'].create({
                            'employee_id': employee.id,
                            'punch_time': utc_dt,
                            'punch_state': punch_state_str,
                            'state': 'unprocessed',
                        })

                if not response.json().get("next"):
                    break

                page += 1
        return {
            'ok': True,
            'message': 'punches fetched successfully.' if not error else 'punches fetched with errors.',
        }

    @api.model
    def fetch_zkteco_punches_one_month(self):
        config = self.env['ir.config_parameter'].sudo()
        url = config.get_param('zkteco.url')
        username = config.get_param('zkteco.username')
        password = config.get_param('zkteco.password')

        if not url or not username or not password:
            return

        today = datetime.today()
        start_date = today - timedelta(days=30)
        end_date = today

        start_date_str = start_date.strftime("%Y-%m-%d")
        end_date_str = end_date.strftime("%Y-%m-%d")

        auth_response = requests.post(
            f"{url.rstrip('/')}/jwt-api-token-auth/",
            json={"username": username, "password": password},
            headers={"Content-Type": "application/json"}
        )
        if auth_response.status_code != 200:
            return

        token = auth_response.json().get("token")
        headers = {
            "Authorization": f"JWT {token}",
            "Content-Type": "application/json"
        }

        attendance_url = f"{url.rstrip('/')}/iclock/api/transactions/"
        local_tz = pytz.timezone("Africa/Tripoli")
        employees = self.env['hr.employee'].search([('ztkeco_id', '!=', False)])

        for employee in employees:
            unprocessed_exists = self.env['ztkeco.punch'].search_count([
                ('employee_id', '=', employee.id),
                ('state', '!=', 'processed')
            ])
            if unprocessed_exists:
                continue

            page = 1
            while True:
                response = requests.get(attendance_url, headers=headers, params={
                    "emp_code": employee.ztkeco_id,
                    "page": page,
                    "page_size": 100,
                    "start_date": start_date_str,
                    "end_date": end_date_str
                })

                if response.status_code != 200:
                    break

                punches = response.json().get("data", [])
                if not punches:
                    break

                for entry in punches:
                    punch_time = entry.get("punch_time")
                    punch_state = entry.get("punch_state")
                    if not punch_time or punch_state is None:
                        continue
                    local_dt = local_tz.localize(datetime.strptime(punch_time, "%Y-%m-%d %H:%M:%S"))
                    utc_dt = local_dt.astimezone(pytz.utc).replace(tzinfo=None)
                    if utc_dt < start_date or utc_dt > end_date:
                        continue
                    punch_state_str = 'checkin' if str(punch_state) == '0' else 'checkout'

                    exists = self.env['ztkeco.punch'].search([
                        ('employee_id', '=', employee.id),
                        ('punch_time', '=', utc_dt)
                    ], limit=1)
                    if not exists:
                        self.env['ztkeco.punch'].create({
                            'employee_id': employee.id,
                            'punch_time': utc_dt,
                            'punch_state': punch_state_str,
                            'state': 'unprocessed',
                        })
                if not response.json().get("next"):
                    break
                page += 1

class ZKTecoPunchProcessor(models.Model):
    _inherit = 'ztkeco.punch'

    @api.model
    def process_zkteco_punches(self, date_from, date_to, employees):
        unprocessed_punches = self.search([('state', '=', 'unprocessed')])
        tz_name = "Africa/Tripoli"  # Set the timezone explicitly to Africa/Tripoli
        errors = []

        try:
            local_tz = pytz.timezone(tz_name)
        except pytz.UnknownTimeZoneError:
            local_tz = pytz.utc

        for employee in employees:
            employee_punches = unprocessed_punches.filtered(lambda p: p.employee_id.id == employee.id).sorted(
                key=lambda p: p.punch_time)

            if not employee_punches:
                continue  # Skip processing if no punches

            work_schedule = employee.resource_calendar_id
            working_days = {int(att.dayofweek) for att in work_schedule.attendance_ids} if work_schedule else set()

            attendance_records = self.env['hr.attendance'].search([
                ('employee_id', '=', employee.id),
                ('check_in', '>=', date_from),
                ('check_in', '<=', date_to)
            ])

            # Create set of existing attendance dates
            existing_attendance_dates = set()
            for record in attendance_records:
                record_date_utc = record.check_in
                record_date_local = pytz.utc.localize(record_date_utc).astimezone(local_tz)
                existing_attendance_dates.add(record_date_local.date())

            current_date = date_from
            while current_date <= date_to:
                try:
                    if current_date.weekday() in working_days:
                        has_punch = any(punch.punch_time.date() == current_date for punch in employee_punches)
                        has_attendance = current_date in existing_attendance_dates

                        if not has_punch and not has_attendance:
                            # Create fallback attendance at 8:00 AM
                            checkin = local_tz.localize(datetime.combine(current_date, time(8, 0, 0)))
                            checkout = checkin + timedelta(seconds=1)

                            # Convert to UTC for storage
                            checkin_utc = checkin.astimezone(pytz.utc).replace(tzinfo=None)
                            checkout_utc = checkout.astimezone(pytz.utc).replace(tzinfo=None)

                            self.env['hr.attendance'].create({
                                'employee_id': employee.id,
                                'check_in': checkin_utc,
                                'check_out': checkout_utc,
                            })
                            existing_attendance_dates.add(current_date)
                except Exception as e:
                    # Formatted to match the new error structure
                    errors.append({
                        'employee name': employee.name,
                        'date': str(current_date),
                        'attendance creation error message': f"Error creating fallback attendance: {e}"
                    })
                current_date += timedelta(days=1)
            punches_by_date = {}
            for punch in employee_punches:
                punch_date = punch.punch_time.date()
                if punch_date not in punches_by_date:
                    punches_by_date[punch_date] = []
                punches_by_date[punch_date].append(punch)

            for date, punches in punches_by_date.items():
                punches_sorted = sorted(punches, key=lambda p: p.punch_time)
                
                pending_checkin = None
                last_checkout = None

                for punch in punches_sorted:
                    # We store normalized values in `fetch_zkteco_punches_date_range`: 'checkin' / 'checkout'
                    is_checkin = punch.punch_state in ['checkin', 'check_in', 'in', 'I', '0']
                    is_checkout = punch.punch_state in ['checkout', 'check_out', 'out', 'O', '1']

                    if is_checkin:
                        if pending_checkin:
                            errors.append({
                                'employee name': employee.name,
                                'date': str(date),
                                'attendance creation error message': f"Duplicated check-ins found at {pending_checkin.punch_time} and {punch.punch_time}."
                            })
                        pending_checkin = punch
                        last_checkout = None

                    elif is_checkout:
                        if not pending_checkin:
                            time_context = f"{last_checkout.punch_time} and {punch.punch_time}" if last_checkout else f"{punch.punch_time} (no preceding check-in)"
                            errors.append({
                                'employee name': employee.name,
                                'date': str(date),
                                'attendance creation error message': f"Duplicated or invalid check-outs found at {time_context}."
                            })
                        else:
                            try:
                                self.env['hr.attendance'].create({
                                    'employee_id': employee.id,
                                    'check_in': pending_checkin.punch_time,
                                    'check_out': punch.punch_time,
                                })
                            except Exception as e:
                                errors.append({
                                    'employee name': employee.name,
                                    'date': str(date),
                                    'attendance creation error message': f"Database error creating attendance: {e}"
                                })
                            
                            # Reset pending check-in after a successful pair
                            pending_checkin = None
                        
                        # Track last check-out for error messages
                        last_checkout = punch

                    # Mark punch as processed
                    punch.state = 'processed'

        return {
            'ok': True,
            'message': 'attendances processed successfully.' if not errors else 'attendances processed with errors.',
            'errors': errors,
        }

    @api.model
    def clean_old_processed_punches(self):
        """
        Delete all staging punches.

        We intentionally use SQL here to avoid ORM `unlink()` side effects that can
        trigger recomputations/flushes on unrelated models (e.g., hr.attendance),
        which may fail if there is bad data (like an invalid employee timezone).
        """
        table = self._table  # typically: ztkeco_punch
        self.env.cr.execute(f'DELETE FROM {table}')
        _logger.info('All ZKTeco punch records have been deleted from %s.', table)

    @api.model
    def cron_fetch_zkteco_punches(self):
        self.env['ztkeco.sync'].fetch_zkteco_punches()

    @api.model
    def cron_process_zkteco_punches(self):
        self.process_zkteco_punches()

    @api.model
    def cron_clean_zkteco_punches(self):
        self.clean_old_processed_punches()
