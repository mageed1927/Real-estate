from datetime import datetime
from odoo import http
from odoo.http import request
from odoo.addons.mataa_base.controllers.common.BaseApiResponse import BaseApiResponse
from odoo.addons.mataa_base.controllers.utility.auth_required import auth_required


class VendorController(http.Controller):
    @http.route('/api/test/vendor/<int:vendor_id>/rfq', type='http', auth='public', methods=['GET'], csrf=False)
    def get_vendor_rfqs(self, vendor_id, page=1, page_size=10):
        # Convert pagination parameters to integers
        page = int(page)
        page_size = int(page_size)
        offset = (page - 1) * page_size
        limit = page_size

        vendor = request.env['res.partner'].sudo().search([('id', '=', vendor_id)], limit=1)
        if not vendor:
            return BaseApiResponse.error(message="Vendor not found", status=404)

        total_count = request.env['purchase.order'].sudo().search_count([
            ('partner_id', '=', vendor_id),
            ('state', '=', 'draft')  # 'draft' state indicates RFQs
        ])

        rfqs = request.env['purchase.order'].sudo().search([
            ('partner_id', '=', vendor_id),
            ('state', '=', 'draft')
        ], limit=limit, offset=offset)

        fields_to_read = ['id', 'name', 'date_order', 'partner_id', 'amount_total', 'order_line']
        rfqs_data = rfqs.read(fields_to_read)

        for rfq in rfqs_data:
            lines = request.env['purchase.order.line'].sudo().browse(rfq.get('order_line', []))
            order_lines_data = lines.read(['id', 'product_id', 'product_qty', 'price_unit', 'price_subtotal'])

            for line in order_lines_data:
                product = request.env['product.product'].sudo().browse(line['product_id'][0])
                product_data = product.read(['id', 'name', 'default_code', 'lst_price', 'product_template_attribute_value_ids'])[0]

                if product_data['product_template_attribute_value_ids']:
                    attribute_values = request.env['product.template.attribute.value'].sudo().browse(product_data['product_template_attribute_value_ids'])
                    product_data['product_template_attribute_value_ids'] = attribute_values.read(['id', 'name', 'attribute_id'])
                line['product_id'] = product_data

            rfq['order_line'] = order_lines_data

            if isinstance(rfq.get('date_order'), datetime):
                rfq['date_order'] = rfq['date_order'].isoformat()

        meta = {
            'total_count': total_count,
            'page': page,
            'page_size': page_size,
            'total_pages': (total_count + page_size - 1) // page_size
        }

        return BaseApiResponse.success(data=rfqs_data, meta=meta)