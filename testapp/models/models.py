# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import ValidationError


class TestApp(models.Model):
    _name = 'my.app'
    _description = 'Hello world'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='My Name', required=True, tracking=True)
    value = fields.Integer(default=30)
    value2 = fields.Float()
    description = fields.Text(default='enter the DES')
    trueFalse = fields.Boolean(default=True)
    html = fields.Html()
    date = fields.Date()
    date_time = fields.Datetime()
    binary = fields.Binary()
    selection = fields.Selection([('1', 'Val1'), ('2', 'Val2'), ('3', 'Val3')], default='1')
    col1 = fields.Float(string='Val 01')
    col2 = fields.Float(string='val 02')
    result = fields.Float(string='val1 + val2', readonly=True)
    computed = fields.Float(readonly=True, compute='_value_pc', store=True)
    state = fields.Selection([('new', 'New'), ('reviewed', 'Reviewed'), ('approved', 'Approved'), ('refused', 'Refused')], default='new')

    _sql_constraints = [
        ('uniq_name', 'unique(name)', 'this name is already here!')
    ]

    # ('uniq_name', 'null' or 'check(0==0)' , 'this name is already here!')

    @api.constrains('value')
    def _check_age(self):
        if self.value <= 26 or self.value >= 36:
            raise ValidationError('age must between 25 and 35')

    @api.onchange('col1')
    def on_change_value(self):
        self.result = self.col1 + self.col2

    @api.depends('result')
    def _value_pc(self):
        for record in self:
            record.computed = float(record.result) / 100

    def event_reviewed(self):
        self.state = 'reviewed'

    def event_approved(self):
        self.state = 'approved'

    def event_refused(self):
        self.state = 'refused'
