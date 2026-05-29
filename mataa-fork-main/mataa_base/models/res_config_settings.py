# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    mataa_in_stock_locations_ids = fields.Many2many('stock.location', related='company_id.mataa_in_stock_locations_ids', readonly=False,
                                             help='Select in-stock locations test.')

    mataa_instock_products_auto_tags = fields.Many2many('product.tag', related='company_id.mataa_instock_products_auto_tags',
                                                    readonly=False,
                                                    help='Select automatic tags that would be set on products when instock')


class Company(models.Model):
    _inherit = "res.company"

    mataa_in_stock_locations_ids = fields.Many2many('stock.location', help='Select in-stock locations test.')
    mataa_instock_products_auto_tags = fields.Many2many('product.tag', help='Select automatic tags that would be set on products when instock')

