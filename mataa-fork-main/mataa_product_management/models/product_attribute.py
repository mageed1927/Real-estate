# -*- coding: utf-8 -*-

from odoo import models, fields, api


class Attribute(models.Model):
    _inherit = 'product.attribute'

    _sql_constraints = [
        ('name_unique', 'unique(name)', 'Product attribute name must be unique!')
    ]

    mataa_slug = fields.Char("Mataa Slug")
    mataa_variant_creation_mode = fields.Boolean("mataa variant creation mode", default=False)

    def write(self, vals):

        return super(Attribute, self).write(vals)

    @api.model
    def create(self, vals):

        return super(Attribute, self).create(vals)
