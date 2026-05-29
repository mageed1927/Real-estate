# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError

class AccountJournal(models.Model):
    _inherit = 'account.journal'

    payment_method_description = fields.Text(
        string='Payment Method Description',
        tracking=True
    )

    e_payment_journal = fields.Boolean(
        string='e-Payment Journal',
        help='Enable this option for e-Payment Journal'
    )
    fee_percentage = fields.Float(
        string="Fee Percentage (%)",
        digits=(16, 6),
        help='1%'
    )
    fee_account_id = fields.Many2one(
        'account.account',
        string='Fee Account',
        domain=[('account_type', '=', 'expense')]
    )