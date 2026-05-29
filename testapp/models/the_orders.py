
from odoo import models, fields, api


class MyOrders(models.Model):
    _name = 'my.order'

    name = fields.Char()
    date_time = fields.Datetime()
    items_ids = fields.One2many('my.orders.items', 'order_id')
    state = fields.Selection([('new', 'New'), ('ready', 'Ready')], default='new')
    isActive = fields.Boolean(default=True)

    def event_ready(self):
        self.state = 'ready'

    def add_item(self):
        self.env['my.orders.items'].create({
            'name': 'test item',
            'itemPrice': 200,
            'qty': 1,
            'order_id': self.id
        })

    def get_query(self):
        query_rst = self.env['my.orders.items'].search([('qty', '>', 1)])
        for item in query_rst:
            print(item.name)


class MyOrdersItems(models.Model):
    _name = 'my.orders.items'

    name = fields.Char()
    itemPrice = fields.Float()
    qty = fields.Integer()
    order_id = fields.Many2one('my.order', domain="[('state', '=', 'ready'), ('isActive', '=', True)]")
