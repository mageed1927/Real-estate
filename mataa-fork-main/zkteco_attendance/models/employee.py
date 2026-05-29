from odoo import models, fields, api

class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    ztkeco_id = fields.Char(string="ZKTeco ID", help="Employee ID in ZKTeco system")
    time_off_balance = fields.Float(string="Time Off Balance",default=0,help="Yearly available time off days.", tracking=True)

    @api.model
    def increase_time_off_balance_monthly(self):
        employees = self.search([])
        for employee in employees:
            employee.time_off_balance += 2.5

    def _create_work_contacts(self):
        for employee in self:
            if not employee.work_contact_id:
                try:
                    contact_vals = {
                        'name': employee.name,
                        'email': employee.work_email or False,
                        'phone': employee.work_phone or False,
                        'is_company': False,
                    }
                    work_contact = self.env['res.partner'].create(contact_vals)
                    employee.work_contact_id = work_contact.id
                except Exception as e:
                    continue