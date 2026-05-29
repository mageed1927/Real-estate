# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request


class EMSProductController(http.Controller):

    @http.route('/api/v1/product/update_by_sku', type='json', auth='public', methods=['POST'], csrf=False)
    def update_product_by_sku(self):
        # 1. Security Check
        api_key = request.httprequest.headers.get('X-API-KEY')
        expected_key = request.env['ir.config_parameter'].sudo().get_param('mataa_order_management.api_key')

        if not api_key or api_key != expected_key:
            return {"status": "error", "message": "Invalid or missing API key.", "code": 401}

        # 2. Get Data from JSON-RPC params
        data = request.params

        try:
            # 3. Call the Model Logic
            result = request.env['external.sync'].sudo().sync_ems_product_by_sku(data)
            return result
        except Exception as e:
            return {"status": "error", "message": str(e)}