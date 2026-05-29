from odoo import models, fields, api


class HrContractAllowance(models.Model):
    _name = 'hr.contract.allowance'
    _description = 'Contract Allowance Line'

    contract_id = fields.Many2one('hr.contract', string='Contract')
    salary_rule_id = fields.Many2one('hr.salary.rule', string='Salary Rule', required=True,
                                     domain="[('category_id.code', 'in', ['ALW', 'BASIC'])]")

    amount = fields.Float(string='Amount', required=True)
    note = fields.Char(string='Note')




class HrContractDeduction(models.Model):
    _name = 'hr.contract.deduction'
    _description = 'Monthly Deduction Line'

    contract_id = fields.Many2one('hr.contract', string='Contract')
    salary_rule_id = fields.Many2one('hr.salary.rule', string='Salary Rule', required=True,
                                     domain="[('category_id.code', '=', 'DED')]")

    amount = fields.Float(string='Amount', required=True)
    date = fields.Date(string='Date', required=True, default=fields.Date.context_today)
    note = fields.Char(string='Note')
    is_processed = fields.Boolean(string="Processed", default=False, readonly=True)


class HrContract(models.Model):
    _inherit = 'hr.contract'

    allowance_ids = fields.One2many('hr.contract.allowance', 'contract_id', string='Allowances')
    deduction_ids = fields.One2many(
        'hr.contract.deduction',
        'contract_id',
        string='Monthly Deductions',
        domain=[('is_processed', '=', False)]
    )
    display_deduction_history = fields.Boolean(string="Show Processed Deductions (archive)", default=False)
    deduction_history_ids = fields.One2many('hr.contract.deduction', 'contract_id', string='Deductions History')
