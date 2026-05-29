# -*- coding: utf-8 -*-

from odoo import models, fields, api


class Example(models.Model):
    _name = 'mataa.test.example'
    _description = 'example of mataa.test.example model'

    name = fields.Char()
    value = fields.Integer()
    value2 = fields.Float(compute="_value_pc", store=True)
    description = fields.Text()

    @api.depends('value')
    def _value_pc(self):
        for record in self:
            record.value2 = float(record.value) / 100

