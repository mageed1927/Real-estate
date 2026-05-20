# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError

class testapp(models.Model):
    _name = 'my.app'
    _description = 'N/A'
    _inherit = ['mail.thread','mail.activity.mixin']

    name = fields.Char(string="My Name", required=True, tracking=True)
    value = fields.Integer(default=30)
    value2 = fields.Float()
    description = fields.Text(default="ENTER DESCRIPTION")
    truefalse = fields.Boolean(default=True)
    html = fields.Html()
    date = fields.Date()
    date_time = fields.Datetime()
    binary = fields.Binary()
    selection = fields.Selection([
        ('1', 'val1'),
        ('2', 'val2'),
        ('3', 'val3'),
        ('4', 'val4')
    ])
    state = fields.Selection([('new','New'),('reviewed','Reviewed'),('approved','Approved'),('refused','Refused')],default='new')

    cal1 = fields.Float(string="val 01")
    cal2 = fields.Float(string="val 02")
    result = fields.Float(string="val1 + val2", compute='_value_pc')
    computed = fields.Float(string="Computed", compute='_compute_value')

    _sql_constraints = [
        ('uniq_name','unique(name)','name is taken',)
    ]
    @api.constrains('value')
    def _check_age(self):
        if self.value <= 18 or self.value >= 36:
            raise ValidationError('age must be between 18 and 36')
    @api.depends('cal1', 'cal2')
    def _value_pc(self):
        for record in self:
            record.result = record.cal1 + record.cal2

    @api.depends('value')
    def _compute_value(self):
        for record in self:
            record.computed = float(record.value) / 100

    def button_action(self):
        pass

    @api.depends('cal1', 'cal2')
    def _compute_result(self):
        for record in self:
            record.result = (record.cal1 + record.cal2) / 100
    def event_reviewed(self):
        self.state = 'reviewed'

    def event_approved(self):
        self.state = 'approved'

    def event_refused(self):
        self.state = 'refused'

    def event_new(self):
        self.state = 'new'