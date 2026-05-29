# -*- coding: utf-8 -*-
import random

from odoo import models, fields, api, _
from odoo.exceptions import UserError

class SOBundle(models.Model):
    _name = 'so.bundle'
    _description = 'Sale Order Bundle'
    _sql_constraints = [
        ('name_unique', 'unique(name)', 'You are not allowed to create duplicate bundle.')
    ]
    name = fields.Char('Bundle Name', required=True)

    mataa_bundled_so_ids = fields.One2many(
        'sale.order',
        'mataa_bundle_id',
        string='Mataa Bundled SOs', copy=False, readonly=True
    )
