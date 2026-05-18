# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.addons.account_consolidation.report.builder import default


class testapp(models.Model):
    _name = 'my.app'
    _description = 'N/A'

    def button_action(self):
        pass

    name = fields.Char(string="My Name", required=True, placeholder='enter name')
    value = fields.Integer(default=30)
    value2 = fields.Float()
    description = fields.Text(default="ENTER DESCRIPTION")
    truefalse = fields.Boolean(default=True)
    html = fields.Html()
    date = fields.Date()
    date_time = fields.Datetime()
    binary = fields.Binary()
    selection = fields.Selection([('1', 'val1'), ('2', 'val2'), ('3', 'val3'), ('4', 'val4')])


class Myorders(models.Model):
    _name = 'my.orders'
    _description = 'My orders'
    name = fields.Char()
    date_time = fields.Datetime()
    items_ids = fields.One2many('my.orders.items', 'order_id', required=True)


class MyOrdersitems(models.Model):
    _name = 'my.orders.items'
    name = fields.Char()
    itemPrice = fields.Float()
    qty = fields.Integer()
    order_id = fields.Many2one('my.orders')

    # @api.depends('value')
    # def _value_pc(self):
    #   for record in self:
    #       record.value2 = float(record.value) / 100
