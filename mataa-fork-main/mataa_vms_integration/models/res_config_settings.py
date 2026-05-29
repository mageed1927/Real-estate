# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    account_payable_inhouse_id = fields.Many2one(
        'account.account',
        related='company_id.property_account_payable_inhouse_id',
        readonly=False,
        string='Payable Account for In-House Vendor',
        domain="[('account_type', '=', 'liability_payable')]",
        help="This account will be used to record the initial liability for goods received from in-house vendors."
    )

    vendor_clearance_journal_id = fields.Many2one(
        'account.journal',
        string='Vendor Clearance Journal',
        help='Journal to use for vendor clearance entries',
        domain="[('type', '=', 'general')]",
        config_parameter='mataa_vms_integration.vendor_clearance_journal_id'
    )

    vms_auto_clearance = fields.Boolean(
        string='Enable Auto Clearance',
        help='Automatically create clearance entries when orders are closed',
        config_parameter='mataa_vms_integration.vms_auto_clearance',
        default=True
    )

    vms_auto_bill_creation = fields.Boolean(
        string='Enable Auto Bill Creation',
        help='Automatically create vendor bills when orders are closed',
        config_parameter='mataa_vms_integration.vms_auto_bill_creation',
        default=True
    )
