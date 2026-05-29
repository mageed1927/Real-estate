# -*- coding: utf-8 -*-
from odoo import api, fields, models


class LoyaltyReward(models.Model):
    _inherit = 'loyalty.reward'

    discount_type = fields.Selection([
        ('percent', 'Percentage'),
        ('fixed', 'Fixed Amount')
    ], string='Discount Type', default='percent')

    discount_percentage = fields.Float(
        string='Discount Percentage',
        help='Percentage discount to apply on the order total.'
    )

    max_discount_amount = fields.Monetary(
        string='Maximum Discount Amount',
        help='Maximum discount allowed for this coupon.',
        currency_field='currency_id'
    )
