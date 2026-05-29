# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    inhouse_difference_journal_id = fields.Many2one('account.journal',
                                                    related='company_id.inhouse_difference_journal_id',
                                                    readonly=False, help='Select the journal for In-House Products price updates.')

    inhouse_difference_value_account_id = fields.Many2one('account.account',
                                                    related='company_id.inhouse_difference_value_account_id',
                                                    readonly=False, help='Select the account for difference value.')

    restricted_attribute_ids = fields.Many2many(
        'product.attribute',
        string='Restricted Attributes',
        related='company_id.restricted_attribute_ids',
        readonly=False,
        help="Select attributes that should not be added to products."
    )


class Company(models.Model):
    _inherit = "res.company"

    inhouse_difference_journal_id = fields.Many2one('account.journal',
                                                    help='Select the journal for In-House Products price updates.')

    inhouse_difference_value_account_id = fields.Many2one('account.account',
                                                    help='Select the account for difference value.')

    restricted_attribute_ids = fields.Many2many(
        'product.attribute',
        string='Restricted Attributes'
    )

