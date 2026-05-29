from odoo import models, fields, api
from odoo.exceptions import UserError
import io
import pandas as pd
import base64


class ZktecoFetchWizard(models.TransientModel):
    _name = 'ztkeco.fetch.wizard'
    _description = 'Fetch ZKTeco punches by date range'

    date_from = fields.Date(string='From date', required=True)
    date_to = fields.Date(string='To date', required=True)
    employees = fields.Many2many('hr.employee', string='Employees')

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        today = fields.Date.context_today(self)
        res['date_from'] = today.replace(day=1)
        res['date_to'] = today
        return res

    def action_fetch_and_process(self):
        self.ensure_one()
        if self.date_from > self.date_to:
            raise UserError('تاريخ البداية يجب أن يكون قبل أو يساوي تاريخ النهاية.')

        employees_to_process = (
            self.employees
            if self.employees
            else self.env['hr.employee'].search([('ztkeco_id', '!=', False)])
        )

        # 1. Fetch Punches
        sync = self.env['ztkeco.sync']
        fetch_result = sync.fetch_zkteco_punches_date_range(
            self.date_from,
            self.date_to,
            employees_to_process,
        )

        if not fetch_result.get('ok'):
            return self._notify('danger', fetch_result.get('message', 'فشل جلب البصمات.'))

        # 2. Process Punches
        punch_model = self.env['ztkeco.punch']
        process_result = punch_model.process_zkteco_punches(self.date_from, self.date_to, employees_to_process)
        
        if not process_result.get('ok'):
            return self._notify('danger', process_result.get('message', 'فشل المعالجة.'))

        # Cleanup staging punches (don't block the success path if cleanup fails)
        try:
            punch_model.clean_old_processed_punches()
        except Exception:
            pass

        # 3. Handle Errors and Excel Export
        errors = process_result.get('errors') or []
        
        if errors:
            output = io.BytesIO()
            workbook = pd.ExcelWriter(output, engine='openpyxl')
            # `errors` coming from processing is a list of dicts (preferred) or strings.
            first_error = errors[0] if errors else None
            if isinstance(first_error, dict):
                df = pd.DataFrame(errors)
            else:
                df = pd.DataFrame({'error': [str(e) for e in errors]})

            # Avoid exporting an empty-looking sheet
            if df.empty:
                df = pd.DataFrame({'error': ['Unknown error (empty errors payload)']})

            df.to_excel(workbook, index=False, sheet_name='Errors')
            workbook.close()
            output.seek(0)
            
            # Create Attachment (temporary)
            attachment = self.env['ir.attachment'].create({
                'name': f'ZKTeco_Errors_{fields.Date.today()}.xlsx',
                'type': 'binary',
                'datas': base64.b64encode(output.read()),
                'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            })
            
            # Trigger Download
            return {
                'type': 'ir.actions.act_url',
                'url': f'/web/content/{attachment.id}?download=true',
                'target': 'self',
            }

        # 4. Success Case (No Errors)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'ZKTeco',
                'message': 'تمت العملية بنجاح دون أخطاء.',
                'type': 'success',
                'sticky': False,
            },
        }

    def _notify(self, n_type, message):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'ZKTeco',
                'message': message,
                'type': n_type,
                'sticky': True,
            },
        }