# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.tools import float_is_zero, format_amount, format_date, html_keep_url, is_html_empty
from ..services.vendor_notification_service import VendorNotificationService


class MataaSalesCoupons(models.Model):
    _name = 'mataa.sales.coupon'
    _description = 'Mataa Sale Order Payment'

    display_name = fields.Char(compute='_compute_display_name', store=True)

    sale_order_id = fields.Many2one(
        'sale.order',
        string='Sale Order',
        required=True,
        help='Select the related Sale Order'
    )

    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        related='sale_order_id.currency_id',
        store=True,
        help='The currency used in the related Sale Order'
    )

    name = fields.Char()

    code = fields.Char()

    amount_deducted = fields.Monetary(
        string='Amount Deducted',
        currency_field='currency_id',
        help='The deducted amount'
    )

    @api.depends('code', 'amount_deducted')
    def _compute_display_name(self):
        for record in self:
            record.display_name = f"{record.code}: {record.amount_deducted}"
