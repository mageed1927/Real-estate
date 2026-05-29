# -*- coding: utf-8 -*-

from odoo import models, fields

class PriceAdjustmentReason(models.Model):
    _name = 'price.adjustment.reason'
    _description = 'Price Adjustment Reason'
    _order = 'name'

    name = fields.Char(string='Reason', required=True, translate=True)
    active = fields.Boolean(string='Active', default=True, help="Set active to false to hide the reason without removing it.")