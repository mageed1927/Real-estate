from odoo import models, fields, api, _


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    @api.model_create_multi
    def create(self, vals_list):

        employees = super(HrEmployee, self).create(vals_list)

        for emp in employees:
            if emp.work_contact_id:
                vals_to_write = {
                    'is_employee': True,
                    'is_customer': False
                }


                company = emp.company_id or self.env.company
                if company.employee_account_receivable_id:
                    vals_to_write['property_account_receivable_id'] = company.employee_account_receivable_id.id
                if company.employee_account_payable_id:
                    vals_to_write['property_account_payable_id'] = company.employee_account_payable_id.id


                emp.work_contact_id.sudo().write(vals_to_write)

        return employees

    def write(self, vals):
        res = super(HrEmployee, self).write(vals)
        if 'work_contact_id' in vals:
            for emp in self:
                if emp.work_contact_id:
                    vals_to_write = {
                        'is_employee': True,
                        'is_customer': False
                    }

                    company = emp.company_id or self.env.company
                    if company.employee_account_receivable_id:
                        vals_to_write['property_account_receivable_id'] = company.employee_account_receivable_id.id
                    if company.employee_account_payable_id:
                        vals_to_write['property_account_payable_id'] = company.employee_account_payable_id.id

                    emp.work_contact_id.sudo().write(vals_to_write)
        return res