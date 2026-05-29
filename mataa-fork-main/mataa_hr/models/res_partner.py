from odoo import models, fields, api

class ResPartner(models.Model):
    _inherit = 'res.partner'


    is_employee = fields.Boolean(
        string="Is a Employee",
        default=False,
        help="Check this box to mark the partner as an Employee."
    )

    @api.onchange('is_employee')
    def _onchange_is_employee(self):

        if self.is_employee:
            self.is_customer = False
            self.is_supplier = False


            company = self.env.company


            if company.employee_account_receivable_id:
                self.property_account_receivable_id = company.employee_account_receivable_id.id

            if company.employee_account_payable_id:
                self.property_account_payable_id = company.employee_account_payable_id.id