from odoo import models, fields

class StockValuationLayer(models.Model):
    _inherit = 'stock.valuation.layer'

    brand_id = fields.Many2one(
        related='product_id.product_tmpl_id.product_brand_id',
        string='Product Brand',
        store=True, 
        readonly=True
    )

