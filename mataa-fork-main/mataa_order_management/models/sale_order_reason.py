from odoo import fields, models

class SaleOrderReason(models.Model):
    _name = 'sale.order.reason'
    _description = 'Sale Order Cancellation/Refund Reason'
    _order = 'sequence'

    name = fields.Char(string='Reason', required=True, translate=True)
    sequence = fields.Integer(string='Sequence', default=10)
    reason_type = fields.Selection(
        [('refund', 'Refund'), ('cancel', 'Cancel')],
        string='Reason Type', required=True
    )