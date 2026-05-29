# -*- coding: utf-8 -*-

from odoo import http
from odoo.http import request
import json
from odoo.addons.mataa_base.controllers.common.BaseApiResponse import BaseApiResponse
from odoo.addons.mataa_base.controllers.utility.auth_required import auth_required


class VariantController(http.Controller):

    @http.route('/api/variants/<int:variant_id>', type='http', auth='public', methods=['GET'], csrf=False)
    def get_variant(self, variant_id):
        api_key = request.httprequest.headers.get('X-API-KEY')
        expected_api_key = request.env['ir.config_parameter'].sudo().get_param('mataa_order_management.api_key')
        if api_key != expected_api_key:
            return BaseApiResponse.error(message="Invalid or missing API key.", status=401)
        variant = request.env['product.product'].sudo().search([('id', '=', variant_id)])

        if not variant:
            return BaseApiResponse.not_found()

        return BaseApiResponse.success(data=self.get_variant_data(variant.id))

    def get_variant_data(self, variant_id):
        variant = request.env['product.product'].sudo().browse(variant_id)
        variant_regular_price = variant.regular_price if variant.regular_price and variant.regular_price > 0 else variant.lst_price
        variant_sale_price = variant.lst_price if variant.lst_price and variant.lst_price != variant_regular_price else None

        is_on_discount = variant_regular_price != variant_sale_price

        product_quantity = variant.get_mataa_quantity()

        variant_data = {
            'id': variant.id,
            'odooId': variant.id,
            'title': variant.name,
            'price': variant_regular_price if is_on_discount else (variant_sale_price or variant_regular_price),
            'quantity': product_quantity,
            'isOnStock': product_quantity > 0,
            'discountPrice': variant_sale_price if variant_sale_price else (variant_sale_price or variant_regular_price),
            'isActive': True,
            'isOnDiscount': is_on_discount,
            'isPrimary': True,
            'description': variant.description_sale,
            'sku': variant.default_code if variant.default_code else None,
            'barcode': variant.barcode if variant.barcode else None,
            'AttributeOdooId': [attribute_value.id for attribute_value in variant.product_template_attribute_value_ids],
        }
        return variant_data
