# -*- coding: utf-8 -*-
import random

from odoo import models, fields, api, _
from random import randint


class SOTag(models.Model):
    _name = 'so.tag'
    _description = 'Sale Order Tag'

    def _get_default_color(self):
        return randint(1, 11)

    name = fields.Char('Tag Name', required=True, translate=True)
    color = fields.Integer('Color', default=_get_default_color)

    _sql_constraints = [
        ('name_uniq', 'unique (name)', "Tag name already exists!"),
    ]
