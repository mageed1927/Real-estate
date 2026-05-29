# -*- coding: utf-8 -*-
from odoo import models, fields

class StockQuant(models.Model):
    _inherit = 'stock.quant'

    draft_reserved_qty = fields.Float(
        related='product_id.draft_reserved_qty',
        string='Draft Reserved Quantity',
        store=False,
    )