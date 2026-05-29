# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError

class AccountMove(models.Model):
    _inherit = 'account.move'

    related_sale_order_id = fields.Many2one('sale.order', compute="_compute_related_sale_order")
    related_sale_order_count = fields.Integer(compute="_compute_related_sale_order_count")
    total_quantity = fields.Float(string="Total Quantity", compute="_compute_total_quantity", store=True)

    @api.depends('invoice_line_ids.quantity')
    def _compute_total_quantity(self):
        for move in self:
            move.total_quantity = sum(move.invoice_line_ids.mapped('quantity'))


    @api.depends('line_ids.purchase_line_id', 'line_ids.sale_line_ids')
    def _compute_related_sale_order(self):
        for move in self:
            so_ids = self.env['sale.order']
            if move.line_ids.mapped('purchase_line_id'):
                so_ids = move.line_ids.mapped('purchase_line_id.order_id.sale_order_id').ids
            elif move.line_ids.mapped('sale_line_ids'):
                so_ids = move.line_ids.mapped('sale_line_ids.order_id').ids

            if so_ids:
                move.related_sale_order_id = so_ids[0]
            else:
                move.related_sale_order_id = False

    @api.depends('line_ids.purchase_line_id')
    def _compute_related_sale_order_count(self):
        for move in self:
            move.related_sale_order_count = len(move.line_ids.mapped('purchase_line_id.order_id.sale_order_id'))

    def action_view_related_sale_orders(self):
        self.ensure_one()
        po_ids = self.line_ids.purchase_line_id.order_id
        so_ids = po_ids.mapped('sale_order_id')
        result = self.env['ir.actions.act_window']._for_xml_id('sale.action_orders')
        if len(so_ids) > 1:
            result['domain'] = [('id', 'in', so_ids.ids)]
        elif len(so_ids) == 1:
            result['views'] = [(self.env.ref('sale.view_order_form', False).id, 'form')]
            result['res_id'] = so_ids.id
        else:
            result = {'type': 'ir.actions.act_window_close'}
        return result

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            move_type = vals.get('move_type') or self.env.context.get('default_move_type')

            if move_type not in ('out_invoice', 'out_refund'):
                continue

            if 'invoice_line_ids' not in vals:
                continue

            company_id = self.env.company
            if vals.get('company_id'):
                company_id = self.env['res.company'].browse(vals['company_id'])

            discount_account = company_id.mataa_discount_account_id
            shipping_discount_account = company_id.mataa_shipping_discount_account_id

            related_sale_orders = self.env['sale.order']

            total_product_discount_pool = 0.0
            total_shipping_discount_pool = 0.0

            for command in vals['invoice_line_ids']:
                if command[0] == 0 and isinstance(command[2], dict):
                    line_vals = command[2]

                    sale_ids_raw = line_vals.get('sale_line_ids')
                    if not sale_ids_raw:
                        continue

                    target_ids = []
                    for cmd in sale_ids_raw:
                        if isinstance(cmd, (list, tuple)) and len(cmd) >= 2 and cmd[0] == 4:
                            target_ids.append(cmd[1])
                        elif isinstance(cmd, (list, tuple)) and len(cmd) >= 3 and cmd[0] == 6:
                            target_ids.extend(cmd[2])
                        elif isinstance(cmd, int):
                            target_ids.append(cmd)

                    if not target_ids:
                        continue


                    sale_line = self.env['sale.order.line'].sudo().browse(target_ids[0])


                    if sale_line.order_id:
                        related_sale_orders |= sale_line.order_id


                    current_price = line_vals.get('price_unit', 0.0)
                    original_price = sale_line.mataa_original_price

                    if original_price > 0 and original_price > current_price:
                        line_vals['price_unit'] = original_price
                        quantity = line_vals.get('quantity', 1.0)
                        diff = original_price - current_price

                        if sale_line.is_delivery:
                            total_shipping_discount_pool += (diff * quantity)
                        else:
                            total_product_discount_pool += (diff * quantity)

            discount_label = company_id.mataa_discount_label or _('Marketing Discount')
            shipping_discount_label = company_id.mataa_shipping_discount_label or _('Shipping Discount')

            if related_sale_orders:
                order = related_sale_orders[0]

                if order.mataa_coupon_ids:
                    coupon_code = order.mataa_coupon_ids[0].code
                    if coupon_code:
                        discount_label = f"{discount_label} ({coupon_code})"

                if order.shipping_offer_name:
                    shipping_discount_label = f"{shipping_discount_label} ({order.shipping_offer_name})"

            if total_product_discount_pool > 0 and discount_account:
                discount_line_vals = {
                    'name': discount_label,
                    'quantity': 1.0,
                    'price_unit': -total_product_discount_pool,
                    'account_id': discount_account.id,
                    'display_type': 'product',
                }
                vals['invoice_line_ids'].append((0, 0, discount_line_vals))

            if total_shipping_discount_pool > 0 and shipping_discount_account:
                shipping_discount_line_vals = {
                    'name': shipping_discount_label,
                    'quantity': 1.0,
                    'price_unit': -total_shipping_discount_pool,
                    'account_id': shipping_discount_account.id,
                    'display_type': 'product',
                }
                vals['invoice_line_ids'].append((0, 0, shipping_discount_line_vals))

        return super(AccountMove, self).create(vals_list)