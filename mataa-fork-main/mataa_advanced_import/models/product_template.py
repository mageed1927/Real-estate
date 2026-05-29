from odoo import models, fields, api


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    def write(self, vals):
        return super(ProductTemplate, self).write(vals)

    @api.model
    def create(self, vals):
        return super(ProductTemplate, self).create(vals)
