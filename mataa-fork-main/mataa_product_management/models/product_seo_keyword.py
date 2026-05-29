# -*- coding: utf-8 -*-
from odoo import models, fields, api


class ProductSEOKeyword(models.Model):
    _name = 'product.seo.keyword'
    _description = 'Product SEO Keyword'
    
    name = fields.Char(required=True, string='Keyword')
