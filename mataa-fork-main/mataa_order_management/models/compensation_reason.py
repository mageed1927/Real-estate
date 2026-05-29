# -*- coding: utf-8 -*-

from random import randint

from odoo import models, fields


class CompensationReason(models.Model):
    _name = 'compensation.reason'
    _description = 'Compensation Reason'
    _rec_name = 'description'

    description = fields.Text(
        string='Description',
        required=True,
    )

    _sql_constraints = [
        ('description_uniq', 'unique(description)', 'Compensation reason desc must be unique!')
    ]
