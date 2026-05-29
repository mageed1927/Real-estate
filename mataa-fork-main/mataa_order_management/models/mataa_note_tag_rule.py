# -*- coding: utf-8 -*-
from odoo import models, fields

class MataaNoteTagRule(models.Model):
    _name = 'mataa.note.tag.rule'
    _description = 'Customer Note to Tag Rule'

    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    keyword = fields.Char(string='Keyword', required=True, help="keyword in the customer note")
    tag_id = fields.Many2one('so.tag', string='Tag to Apply', required=True, help="tag will be added in the SO tags field")