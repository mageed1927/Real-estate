# -*- coding: utf-8 -*-

from odoo import models, fields

class ResCompany(models.Model):
    _inherit = 'res.company'

    property_account_payable_inhouse_id = fields.Many2one(
        'account.account',
        string='Payable Account for In-House Vendor',
        domain="[('account_type', '=', 'liability_payable')]",
        help="This account will be used to record the initial liability for goods received from in-house vendors."
    )
