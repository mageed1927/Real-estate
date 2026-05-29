# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # TODO : to be reviewed and fixed after new product catalog system
    external_api_base_url = fields.Char(string="Base URL", config_parameter="mataa_external_sync.external_api_base_url")
    customer_key = fields.Char(string="Customer Key", config_parameter="mataa_external_sync.customer_key")
    customer_secret = fields.Char(string="Customer Secret", config_parameter="mataa_external_sync.customer_secret")
    asynchronous_sync = fields.Boolean(string="Disable real time sync",
                                       config_parameter="mataa_external_sync.asynchronous_sync")

    restricted_product_tag_ids = fields.Many2many('product.tag',
                                                 related='company_id.restricted_product_tag_ids',
                                                 readonly=False,
                                                 help='Tags that, when assigned to a product, restrict its syncing/creation')


class Company(models.Model):
    _inherit = "res.company"

    restricted_product_tag_ids = fields.Many2many(
        'product.tag',
        relation='company_restricted_product_tag_rel',
        column1='company_id',
        column2='tag_id',
        string='Restricted Product Tags',
        help='Tags that, when assigned to a product, restrict its syncing/creation')


