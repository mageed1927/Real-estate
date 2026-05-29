# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError


class ProductTrueReference(models.Model):
    _name = 'product.true.reference'
    _description = 'Product True Reference'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    product_product_id = fields.Many2one('product.product', string="Product Variant", tracking=True)
    product_template_id = fields.Many2one('product.template', string="Product Template", store=True,
                                          related="product_product_id.product_tmpl_id", tracking=True)
    regular_price_reference = fields.Float(tracking=True)
    sale_price_reference = fields.Float(tracking=True)

    partner_id = fields.Many2one('res.partner', string="Vendor", tracking=True)
    vendor_price = fields.Float(tracking=True)