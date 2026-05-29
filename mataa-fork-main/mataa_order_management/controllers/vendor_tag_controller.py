# -*- coding: utf-8 -*-

from odoo import http
from odoo.http import request
import json
from odoo.addons.mataa_base.controllers.common.BaseApiResponse import BaseApiResponse
from odoo.addons.mataa_base.controllers.utility.auth_required import auth_required


class VendorController(http.Controller):

    @http.route('/api/vendor_tags', type='http', auth='public', methods=['GET'], csrf=False)
    def get_vendors(self, page=1, page_size=10):
        api_key = request.httprequest.headers.get('X-API-KEY')
        expected_api_key = request.env['ir.config_parameter'].sudo().get_param('mataa_order_management.api_key')
        if api_key != expected_api_key:
            return BaseApiResponse.error(message="Invalid or missing API key.", status=401)
        page = int(page)
        page_size = int(page_size)
        offset = (page - 1) * page_size
        limit = page_size

        vendor_tag_ids = request.env['res.partner.category'].with_context(active_test=False).sudo().search(
            [], limit=limit, offset=offset)

        vendor_tags_data = []
        for tag_id in vendor_tag_ids:
            vendor_tags_data.append(self.get_vendor_tag_data(tag_id.id))

        total_count = len(vendor_tag_ids)
        meta = {
            'total_count': total_count,
            'page': page,
            'page_size': page_size,
            'total_pages': (total_count + page_size - 1) // page_size
        }
        return BaseApiResponse.success(data=vendor_tags_data, meta=meta)

    def get_vendor_tag_data(self, tag_id):
        tag_id = request.env['res.partner.category'].sudo().browse(tag_id)
        vendor_tag_data = {
            'id': tag_id.id,
            'name': tag_id.name,
            'parent_id': tag_id.parent_id.id if tag_id.parent_id.id else None
        }
        return vendor_tag_data
