

# -*- coding: utf-8 -*-
from odoo.exceptions import UserError, ValidationError

from odoo import models, fields, api, _



class ProductOfferTag(models.Model):
    _name = "product.offer.tag"
    _description = "Product Offer Tag"

    name = fields.Char(required=True)
    color = fields.Integer()