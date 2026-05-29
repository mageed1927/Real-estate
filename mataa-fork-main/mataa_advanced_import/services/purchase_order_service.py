import requests

from odoo import api, models
from odoo.exceptions import UserError


class PurchaseOrderService:

    @staticmethod
    def create_order(env, vendor):
        """Create new purchase order"""
        datas = {
            'partner_id': vendor.id,
        }
        picking_type_id = int(env['ir.config_parameter'].sudo().get_param('mataa_advanced_import.import_pick_type_id'))
        if picking_type_id:
            datas.update({
                'picking_type_id': picking_type_id
            })
        order = env['purchase.order'].create(datas)

        return order

    @staticmethod
    def create_order_line(env, order, variant, quantity, price, package_name):
        purchase_line_model = env['purchase.order.line']
        purchase_line_vals = {
            'order_id': order.id,
            'product_id': variant.id,
            'product_qty': quantity,
            'price_unit': price,
            'name': variant.display_name,
        }
        if 'package_name' in purchase_line_model._fields:
            purchase_line_vals.update({
                'package_name': package_name
            })
        purchase_line_model.create(purchase_line_vals)

