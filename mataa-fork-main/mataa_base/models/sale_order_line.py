# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    product_brand_id = fields.Many2one(
        "product.brand", string="Brand", related="product_id.product_brand_id", store=True
    )