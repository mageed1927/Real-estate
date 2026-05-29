# -*- coding: utf-8 -*-

from odoo import models, fields

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    last_discount_reason_id = fields.Many2one(
        'price.adjustment.reason',
        string='Last Discount Reason',
        readonly=True,
        copy=False,
        help="The reason for the last price adjustment."
    )

    last_discount_description = fields.Text(
        string='Last Discount Description',
        readonly=True,
        copy=False
    )
