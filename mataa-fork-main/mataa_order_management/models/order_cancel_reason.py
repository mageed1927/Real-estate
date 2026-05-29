from odoo import models, fields


class OrderCancelReason(models.Model):
    _name = 'order.cancel.reason'
    _description = 'Order Cancel Reason'

    name = fields.Char(string='Reason', required=True)
    active = fields.Boolean(default=True)
