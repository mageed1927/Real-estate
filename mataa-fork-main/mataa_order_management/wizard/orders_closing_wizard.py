# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class OrdersClosingWizard(models.TransientModel):
    _name = 'orders.closing.wizard'
    _description = 'Orders closing wizard'

    sale_order_ids = fields.Many2many(
        'sale.order', default=lambda self: self.env.context.get('active_ids'))
    closing_method_name = fields.Char(required=True)

    number_of_orders = fields.Integer(compute='_compute_values', string='Number of orders')

    total_value_without_delivery = fields.Float(compute='_compute_values', string='Total value without delivery')
    total_delivery_fee = fields.Float(compute='_compute_values', string='Total delivery fee')
    total_value_with_delivery = fields.Float(compute='_compute_values', string='Total value with delivery')

    @api.depends('sale_order_ids')
    def _compute_values(self):
        for wizard in self:
            order_ids = wizard.sale_order_ids
            if wizard.closing_method_name == "finalize_mataa_order":
                order_ids = wizard.sale_order_ids.filtered(lambda order: not order.is_handled)
            elif wizard.closing_method_name == "close_fully_returned_order":
                order_ids = wizard.sale_order_ids.filtered(lambda order: not order.mata_shipment_state)
            order_lines = order_ids.mapped('order_line').filtered(lambda line: not line.is_delivery)
            delivery_lines = order_ids.mapped('order_line').filtered(lambda line: line.is_delivery)

            wizard.number_of_orders = len(order_ids)

            wizard.total_value_without_delivery = sum(order_lines.mapped('price_total'))
            wizard.total_delivery_fee = sum(delivery_lines.mapped('price_total'))

            wizard.total_value_with_delivery = sum(order_ids.mapped('amount_total'))

    def close_orders(self):
        self.ensure_one()
        if hasattr( self.sale_order_ids, self.closing_method_name):
            getattr(self.sale_order_ids.with_context(skip_closing_confirmation=True),
                    self.closing_method_name)()
