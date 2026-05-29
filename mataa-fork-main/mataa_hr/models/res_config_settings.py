from odoo import models, fields

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    employee_account_receivable_id = fields.Many2one(
        related='company_id.employee_account_receivable_id',
        readonly=False
    )
    employee_account_payable_id = fields.Many2one(
        related='company_id.employee_account_payable_id',
        readonly=False
    )


class ResCompany(models.Model):
    _inherit = 'res.company'

    employee_account_receivable_id = fields.Many2one(
        'account.account',
        string="Default Employee Receivable Account",
        domain="[('deprecated', '=', False)]"
    )
    employee_account_payable_id = fields.Many2one(
        'account.account',
        string="Default Employee Payable Account",
        domain="[('deprecated', '=', False)]"
    )