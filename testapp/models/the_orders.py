from odoo import models, fields, api

class Myorders(models.Model):
    _name = 'my.orders'
    _description = 'My orders'
    name = fields.Char()
    date_time = fields.Datetime()
    items_ids = fields.One2many('my.orders.items', 'order_id', required=True)
    state = fields.Selection(
        [('new', 'New'), ('ready', 'Ready')], default='new')
    isActive = fields.Boolean(default=True)
    def event_ready(self):
        self.state= 'ready'


class MyOrdersitems(models.Model):
    _name = 'my.orders.items'
    name = fields.Char()
    itemPrice = fields.Float()
    qty = fields.Integer()
    order_id = fields.Many2one('my.orders', domain="[('state','=','ready'),('isActive','=','True')]")

