# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.addons.account_consolidation.report.builder import default


class testapp(models.Model):
    _name = 'my.app'
    _description = 'N/A'

    def button_action(self):
        pass

    name = fields.Char(string="My Name", required=True)
    value = fields.Integer(default=30)
    value2 = fields.Float()
    description = fields.Text(default="ENTER DESCRIPTION")
    truefalse = fields.Boolean(default=True)
    html = fields.Html()
    date = fields.Date()
    date_time = fields.Datetime()
    binary = fields.Binary()
    selection = fields.Selection([('1', 'val1'), ('2', 'val2'), ('3', 'val3'), ('4', 'val4')])

    cal1 = fields.Float(string="val 01")
    cal2 = fields.Float(string="val 02")
    result = fields.Float(string="val1 + val2", compute='_value_pc')

    @api.depends('cal1', 'cal2')
    def _value_pc(self):
        self.result = self.cal1 + self.cal2
     #for record in self:
     #record.value2 = float(record.value) / 100
