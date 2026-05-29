# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class DeliveryCarrier(models.Model):
    _inherit = "delivery.carrier"

    carrier_partner_id = fields.Many2one('res.partner', string='Service Provider', tracking=True)
    cod_journal_id = fields.Many2one('account.journal', string='COD Journal', tracking=True,
                                     domain="[('type', '=', 'cash')]")
    transfer_fee_product_id = fields.Many2one(
        'product.product',
        string='Transfer Fee Product',
        domain="[('type', '=', 'service')]",
        help="The service product used to invoice transfer fees for this carrier."
    )