from odoo import models, fields, api


class ProductProduct(models.Model):
    _inherit = 'product.product'

    def write(self, vals):
        return super(ProductProduct, self).write(vals)

    @api.model
    def create(self, vals):
        return super(ProductProduct, self).create(vals)
