# -*- coding: utf-8 -*-

import json
from odoo import http
from odoo.http import request

# الآن سنعود لاستخدام BaseApiResponse لأنه سيعمل بشكل صحيح
from odoo.addons.mataa_base.controllers.common.BaseApiResponse import BaseApiResponse
from ..services.product_service import ProductService


class ProductApiController(http.Controller):

    @http.route('/api/products/quantity_check', type='http', auth='public', methods=['POST'], csrf=False)
    def check_product_quantity(self, **kw):
        try:

            data = json.loads(request.httprequest.data)
            mataa_ids = data.get('mataa_ids')

            if not isinstance(mataa_ids, list):

                return BaseApiResponse.bad_request(message="Payload must contain a 'mataa_ids' list.")

            response_data = ProductService.get_quantities_by_mataa_ids(mataa_ids)


            return BaseApiResponse.success(data=response_data)

        except Exception as e:

            return BaseApiResponse.error(message=str(e), status=500)

    @http.route('/api/product/<int:product_id>/info', type='http', auth='public', methods=['GET'], csrf=False)
    def get_product_info(self, product_id):
        api_key = request.httprequest.headers.get('X-API-KEY')
        expected_api_key = request.env['ir.config_parameter'].sudo().get_param('mataa_order_management.api_key')
        if api_key != expected_api_key:
            return request.make_response(
                json.dumps({"error": "Invalid or missing API key."}),
                headers=[('Content-Type', 'application/json')],
                status=401
            )
        try:
            if not product_id:
                return BaseApiResponse.error(message="Missing product_id")

            response_data = ProductService.get_product_template_info(self,product_id)

            if not response_data:
                return BaseApiResponse.error(message="Product not found", status=404)

            return BaseApiResponse.success(data=response_data)

        except Exception as e:
            return BaseApiResponse.error(message=str(e), status=500)

    @http.route('/api/barcode/<string:barcode>/info', type='http', auth='public', methods=['GET'], csrf=False)
    def get_product_info_by_barcode(self, barcode):
        api_key = request.httprequest.headers.get('X-API-KEY')
        expected_api_key = request.env['ir.config_parameter'].sudo().get_param('mataa_order_management.api_key')
        if api_key != expected_api_key:
            return request.make_response(
                json.dumps({"error": "Invalid or missing API key."}),
                headers=[('Content-Type', 'application/json')],
                status=401
            )
        try:
            if not barcode:
                return BaseApiResponse.error(message="Missing barcode")

            response_data = ProductService.get_product_variant_info_by_barcode(self, barcode)

            if not response_data:
                return BaseApiResponse.error(message="Product with given barcode not found", status=404)

            return BaseApiResponse.success(data=response_data)

        except Exception as e:
            return BaseApiResponse.error(message=str(e), status=500)

    @http.route('/api/product_variant/<int:variant_id>/info', type='http', auth='public', methods=['GET'], csrf=False)
    def get_variant_info(self, variant_id):
        api_key = request.httprequest.headers.get('X-API-KEY')
        expected_api_key = request.env['ir.config_parameter'].sudo().get_param('mataa_order_management.api_key')
        if api_key != expected_api_key:
            return request.make_response(
                json.dumps({"error": "Invalid or missing API key."}),
                headers=[('Content-Type', 'application/json')],
                status=401
            )
        try:

            if not variant_id:
                return BaseApiResponse.error(message="Missing variant_id")

            response_data = ProductService.get_product_variant_info(self,variant_id)

            if not response_data:
                return BaseApiResponse.error(message="Variant not found", status=404)

            return BaseApiResponse.success(data=response_data)

        except Exception as e:
            return BaseApiResponse.error(message=str(e), status=500)

    @http.route('/api/attribute_value/<int:value_id>/info', type='http', auth='public', methods=['GET'], csrf=False)
    def get_attribute_value_info(self, value_id):
        api_key = request.httprequest.headers.get('X-API-KEY')
        expected_api_key = request.env['ir.config_parameter'].sudo().get_param('mataa_order_management.api_key')

        if api_key != expected_api_key:
            return request.make_response(
                json.dumps({"error": "Invalid or missing API key."}),
                headers=[('Content-Type', 'application/json')],
                status=401
            )

        try:
            if not value_id:
                return BaseApiResponse.error(message="Missing value_id")

            value_record = request.env['product.attribute.value'].sudo().browse(value_id)

            if not value_record.exists():
                return BaseApiResponse.error(message="Attribute Value not found", status=404)


            response_data = {
                "key": value_record.attribute_id.name,
                "value": value_record.name,
                "Id": str(value_record.id)
            }

            return BaseApiResponse.success(data=response_data)

        except Exception as e:
            return BaseApiResponse.error(message=str(e), status=500)