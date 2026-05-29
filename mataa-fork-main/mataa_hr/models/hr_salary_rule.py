from odoo import models, fields

class HrSalaryRule(models.Model):
    _inherit = 'hr.salary.rule'

    take_partner = fields.Boolean(
        string="Take From Partner Balance",
        default=False
    )