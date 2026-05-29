# -*- coding: utf-8 -*-

from odoo import http
from odoo.http import request
import json
from odoo.addons.mataa_base.controllers.common.BaseApiResponse import BaseApiResponse
from odoo.addons.mataa_base.controllers.utility.auth_required import auth_required


class VendorController(http.Controller):

    @http.route('/api/vendors', type='http', auth='public', methods=['GET'], csrf=False)
    def get_vendors(self, page=1, page_size=10):
        api_key = request.httprequest.headers.get('X-API-KEY')
        expected_api_key = request.env['ir.config_parameter'].sudo().get_param('mataa_order_management.api_key')
        if api_key != expected_api_key:
            return BaseApiResponse.error(message="Invalid or missing API key.", status=401)
        page = int(page)
        page_size = int(page_size)
        offset = (page - 1) * page_size
        limit = page_size

        partner_ids = request.env['res.partner'].with_context(active_test=False).sudo().search(
            [('supplier_rank', '>', 0)], limit=limit, offset=offset)

        vendors_data = []
        for partner_id in partner_ids:
            vendors_data.append(self.get_vendor_data(partner_id.id))

        total_count = len(partner_ids)
        meta = {
            'total_count': total_count,
            'page': page,
            'page_size': page_size,
            'total_pages': (total_count + page_size - 1) // page_size
        }
        return BaseApiResponse.success(data=vendors_data, meta=meta)

    @http.route('/api/vendors/<int:vendor_id>', type='http', auth='public', methods=['GET'], csrf=False)
    def get_vendor(self, vendor_id):
        api_key = request.httprequest.headers.get('X-API-KEY')
        expected_api_key = request.env['ir.config_parameter'].sudo().get_param('mataa_order_management.api_key')
        if api_key != expected_api_key:
            return BaseApiResponse.error(message="Invalid or missing API key.", status=401)

        partner_id = request.env['res.partner'].with_context(active_test=False).sudo().search([('id', '=', vendor_id)])

        if not partner_id:
            return BaseApiResponse.not_found()

        return BaseApiResponse.success(data=self.get_vendor_data(partner_id.id))

    @http.route('/api/vendors', type='http', auth='public', methods=['POST'], csrf=False)
    def create_vendor(self):
        api_key = request.httprequest.headers.get('X-API-KEY')
        expected_api_key = request.env['ir.config_parameter'].sudo().get_param('mataa_order_management.api_key')
        if api_key != expected_api_key:
            return BaseApiResponse.error(message="Invalid or missing API key.", status=401)
        data = json.loads(request.httprequest.data)
        try:
            partner_id = request.env['res.partner'].sudo().create({
                'mataa_id': data.get('mataa_id'),
                'name': data.get('name'),
                'city': data.get('area'),
                'is_company': True,
                'supplier_rank': 1,
            })
            if data.get('tags'):
                category_ids = request.env['res.partner.category'].sudo().search([('id', 'in', data.get('tags'))])
                partner_id.category_id = category_ids
            return BaseApiResponse.created(data=self.get_vendor_data(partner_id.id),
                                           message='Vendor created successfully')
        except Exception as e:
            return BaseApiResponse.error(message=str(e))

    @http.route('/api/vendors/<int:vendor_id>', type='http', auth='public', methods=['PUT'], csrf=False)
    def update_vendor(self, vendor_id):
        api_key = request.httprequest.headers.get('X-API-KEY')
        expected_api_key = request.env['ir.config_parameter'].sudo().get_param('mataa_order_management.api_key')
        if api_key != expected_api_key:
            return BaseApiResponse.error(message="Invalid or missing API key.", status=401)
        data = json.loads(request.httprequest.data)
        partner_id = request.env['res.partner'].with_context(active_test=False).sudo().search([('id', '=', vendor_id)])
        if not partner_id:
            return BaseApiResponse.not_found()

        try:
            partner_id.write({
                'name': data.get('name'),
                'city': data.get('area'),
                'working_hours_start': data.get('workingHoursStart'),
                'working_hours_end': data.get('workingHoursEnd')


            })
            if data.get('tags'):
                category_ids = request.env['res.partner.category'].sudo().search([('id', 'in', data.get('tags'))])
                partner_id.category_id = category_ids
            return BaseApiResponse.success(data=self.get_vendor_data(partner_id.id),
                                           message='Vendor updated successfully')
        except Exception as e:
            return BaseApiResponse.error(message=str(e))

    @http.route('/api/vendors/<int:vendor_id>/update_state', type='http', auth='public', methods=['PUT'], csrf=False)
    def update_vendor_state(self, vendor_id):
        api_key = request.httprequest.headers.get('X-API-KEY')
        expected_api_key = request.env['ir.config_parameter'].sudo().get_param('mataa_order_management.api_key')
        if api_key != expected_api_key:
            return BaseApiResponse.error(message="Invalid or missing API key.", status=401)
        data = json.loads(request.httprequest.data)
        partner_id = request.env['res.partner'].with_context(active_test=False).sudo().search([('id', '=', vendor_id)])
        if not partner_id:
            return BaseApiResponse.not_found()

        try:
            partner_id.write({
                'active': data.get('state') == 1,
            })
            return BaseApiResponse.success(data=self.get_vendor_data(partner_id.id),
                                           message='Vendor status updated successfully')
        except Exception as e:
            return BaseApiResponse.error(message=str(e))

    @http.route('/api/vendors/<int:vendor_id>', type='http', auth='public', methods=['DELETE'], csrf=False)
    def delete_vendor(self, vendor_id):
        api_key = request.httprequest.headers.get('X-API-KEY')
        expected_api_key = request.env['ir.config_parameter'].sudo().get_param('mataa_order_management.api_key')
        if api_key != expected_api_key:
            return BaseApiResponse.error(message="Invalid or missing API key.", status=401)
        partner_id = request.env['res.partner'].with_context(active_test=False).sudo().search([('id', '=', vendor_id)])
        if not partner_id:
            return BaseApiResponse.not_found()
        partner_id.soft_delete()
        return BaseApiResponse.no_content(message='Vendor soft deleted successfully')

    # ------------- Vendor RFQs -------------
    @http.route('/api/vendors/<int:vendor_id>/rfqs', type='http', auth='public', methods=['GET'], csrf=False)
    def get_vendor_rfqs(self, vendor_id, page=1, page_size=10, orderby=None, state=None):
        api_key = request.httprequest.headers.get('X-API-KEY')
        expected_api_key = request.env['ir.config_parameter'].sudo().get_param('mataa_order_management.api_key')
        if api_key != expected_api_key:
            return BaseApiResponse.error(message="Invalid or missing API key.", status=401)
        page = int(page)
        page_size = int(page_size)
        offset = (page - 1) * page_size
        limit = page_size

        ordered_by = 'create_date DESC'
        if orderby == 'asc':
            ordered_by = 'create_date ASC'
        domain = [('partner_id', '=', vendor_id)]
        if state:
            domain += [('state', '=', state)]
        order_ids = request.env['purchase.order'].sudo().search(domain, order=ordered_by, limit=limit, offset=offset)

        rfqs_data = []
        for order_id in order_ids:
            rfqs_data.append(self.get_order_data(order_id.id))

        total_count = len(order_ids)
        meta = {
            'total_count': total_count,
            'page': page,
            'page_size': page_size,
            'total_pages': (total_count + page_size - 1) // page_size
        }
        return BaseApiResponse.success(data=rfqs_data, meta=meta)

    @http.route('/api/vendors/<int:vendor_id>/rfqs/<int:rfq_id>', type='http', auth='public', methods=['GET'],
                csrf=False)
    def get_vendor_rfq(self, vendor_id, rfq_id):
        api_key = request.httprequest.headers.get('X-API-KEY')
        expected_api_key = request.env['ir.config_parameter'].sudo().get_param('mataa_order_management.api_key')
        if api_key != expected_api_key:
            return BaseApiResponse.error(message="Invalid or missing API key.", status=401)

        order_id = request.env['purchase.order'].sudo().search([('id', '=', rfq_id), ('partner_id', '=', vendor_id)])

        if not order_id.exists():
            return BaseApiResponse.not_found(message=f"rfq_id wasn't found for this vendor")

        return BaseApiResponse.success(data=self.get_order_data(order_id.id))

    @http.route('/api/vendors/<int:vendor_id>/rfqs/<int:rfq_id>/details', type='http', auth='public', methods=['GET'],
                csrf=False)
    def get_vendor_rfq_lines(self, vendor_id, rfq_id):
        api_key = request.httprequest.headers.get('X-API-KEY')
        expected_api_key = request.env['ir.config_parameter'].sudo().get_param('mataa_order_management.api_key')
        if api_key != expected_api_key:
            return BaseApiResponse.error(message="Invalid or missing API key.", status=401)

        order_id = request.env['purchase.order'].sudo().search([('id', '=', rfq_id), ('partner_id', '=', vendor_id)])

        lines_data = []
        for line in order_id.order_line:
            lines_data.append(self.get_order_line_data(line.id))
        return BaseApiResponse.success(data=lines_data)

    @http.route('/api/vendors/<int:vendor_id>/rfqs/<int:rfq_id>/accept', type='http', auth='public', methods=['PUT'],
                csrf=False)
    def accept_vendor_rfq(self, vendor_id, rfq_id):
        api_key = request.httprequest.headers.get('X-API-KEY')
        expected_api_key = request.env['ir.config_parameter'].sudo().get_param('mataa_order_management.api_key')
        if api_key != expected_api_key:
            return BaseApiResponse.error(message="Invalid or missing API key.", status=401)
        data = json.loads(request.httprequest.data)

        rfq = request.env['purchase.order'].sudo().search([('id', '=', rfq_id), ('partner_id', '=', vendor_id)])
        if not rfq.exists():
            return BaseApiResponse.not_found(message=f"rfq_id wasn't found for this vendor")

        if rfq.state not in ['draft', 'sent']:
            return BaseApiResponse.not_found(message=f"rfq is already accepted")

        available_qty_list = data.get('rfq_lines')

        for item in available_qty_list:
            reason = item.get('reason')
            available_date = item.get('available_date')
            note = item.get('note')

            rfq_line_id = item.get('rfq_line_id')
            if not rfq_line_id:
                return BaseApiResponse.error(message=f"invalid rfq_line_id {rfq_line_id}")

            rfq_line = request.env['purchase.order.line'].sudo().search(
                [('id', '=', rfq_line_id), ('order_id', '=', rfq_id)])
            if not rfq_line.exists():
                return BaseApiResponse.not_found(message=f"rfq_line_id {rfq_line_id} wasn't found")

            available_quantity = item.get('available_quantity')
            if available_quantity is None:
                return BaseApiResponse.error(message=f"invalid line {rfq_line_id} available quantity")

            if available_quantity < 0:
                return BaseApiResponse.error(message=f"invalid line {rfq_line_id} available quantity", errors="available quantity cannot be less than 0")

            if available_quantity > rfq_line.product_qty:
                return BaseApiResponse.error(message=f"invalid line {rfq_line_id} available quantity", errors="available quantity cannot be greater than request requested quantity")

            if available_quantity < rfq_line.product_qty:
                #move this logic to create in the model
                # seller_ids = (rfq_line.product_id.seller_ids.filtered(
                #         lambda s: s.product_id.id == rfq_line.product_id.id and s.partner_id.id == vendor_id and s.published
                #     ))
                #
                # if seller_ids:
                #     seller_ids[0].sudo().write({
                #         'min_qty': 0,
                #     })
                request.env['product.vendor.blacklist'].sudo().create({
                    'product_id': rfq_line.product_id.id,
                    'vendor_id': rfq.partner_id.id,
                    'purchase_order_id': rfq.id,
                    'sale_order_id': rfq.sale_order_id.id,
                    'reason': reason
                })

            rfq_line.sudo().write({
                'available_qty': available_quantity,
                'reason': reason,
                'available_date': available_date,
                'note': note
            })

            new_unit_price = item.get('unit_price')
            if new_unit_price is not None:
                if isinstance(new_unit_price, (int, float)) and new_unit_price >= 0:
                    rfq_line.sudo().write({'price_unit': new_unit_price})
                else:
                    return BaseApiResponse.error(
                        message=f"Invalid unit_price for rfq_line_id {rfq_line_id}. It must be a non-negative number.")

            sale_order_line = request.env['sale.order.line'].sudo().search(
                [('product_id', '=', rfq_line.product_id.id),
                 ('order_id', '=', rfq_line.order_id.sale_order_id.id)]
            )

            # if there are multiple sale order lines for the same product, we need to filter out the ones that have negative quantity from a refund order
            if len(sale_order_line) > 1:
                sale_order_line = sale_order_line.filtered(lambda l: l.product_uom_qty > 0)

            rfq_lines = request.env['purchase.order.line'].sudo().search(
                [('product_id', '=', rfq_line.product_id.id),
                 ('order_id.sale_order_id', '=', rfq_line.order_id.sale_order_id.id)]
            )

            total_available_qty = sum(line.available_qty for line in rfq_lines)

            if sale_order_line and total_available_qty >= sale_order_line.product_uom_qty:
                sale_order_line.sudo().write({'status': 'in_preparing'})

        try:
            rfq.action_split_rfq()
        except Exception as e:
            return BaseApiResponse.error(message=f"{e}")

        rfq.state = 'to approve'

        rfq_lines = data.get('rfq_lines')
        operation_type = request.env['stock.picking.type'].sudo().search([('name', '=', 'Receipts')], limit=1)

        # Check for existing blanket order without an external_id
        existing_blanket_order = request.env['purchase.requisition'].sudo().search([
            ('vendor_id', '=', rfq.partner_id.id),
            ('state', 'not in', ['done', 'cancel']),
            ('prevent_line_addition', '=', False)
        ], limit=1)

        blanket_order_lines = []
        for line in rfq_lines:
            rfq_line = request.env['purchase.order.line'].sudo().browse(line.get('rfq_line_id'))
            if rfq_line.available_qty > 0:
                blanket_order_lines.append({
                    'pol_id': rfq_line.id,
                    'so_id': rfq.sale_order_id.id,
                    'product_id': rfq_line.product_id.id,
                    'product_description_variants': f"SO {rfq.sale_order_id.name} / RFQ {rfq.name}",
                    'product_qty': rfq_line.available_qty,
                    'price_unit': rfq_line.price_unit,
                })

        # Write lines to the existing blanket order
        if existing_blanket_order:
            existing_blanket_order.write({'line_ids': [(0, 0, line) for line in blanket_order_lines]})
            rfq.requisition_id = existing_blanket_order.id  # Associate RFQ with existing blanket order

        else:
            # If no existing blanket order is found, create a new one
            blanket_order_lines = []
            for line in rfq_lines:
                rfq_line = request.env['purchase.order.line'].sudo().browse(line.get('rfq_line_id'))
                if rfq_line.available_qty > 0:
                    blanket_order_lines.append((0, 0, {
                        'pol_id': rfq_line.id,
                        'so_id': rfq.sale_order_id.id,
                        'product_id': rfq_line.product_id.id,
                        'product_description_variants': f"SO {rfq.sale_order_id.name} / RFQ {rfq.name}",
                        'product_qty': rfq_line.available_qty,
                        'price_unit': rfq_line.price_unit,
                    }))

            if len(blanket_order_lines) > 0:
                blanket_order = request.env['purchase.requisition'].sudo().create({
                    'vendor_id': rfq.partner_id.id,
                    'type_id': 1,
                    'picking_type_id': operation_type.id,
                    'line_ids': blanket_order_lines,
                    'origin': rfq.sale_order_id.name if rfq.sale_order_id.name else "undefined SO",
                })

                rfq.requisition_id = blanket_order.id

        return BaseApiResponse.success(data=self.get_order_with_lines_data(rfq_id), message="RFQ was accepted successfully")

    @http.route('/api/vendors/<int:vendor_id>/rfqs/<int:rfq_id>/decline', type='http', auth='public', methods=['PUT'],
                csrf=False)
    def decline_vendor_rfq(self, vendor_id, rfq_id):
        api_key = request.httprequest.headers.get('X-API-KEY')
        expected_api_key = request.env['ir.config_parameter'].sudo().get_param('mataa_order_management.api_key')
        if api_key != expected_api_key:
            return BaseApiResponse.error(message="Invalid or missing API key.", status=401)
        data = json.loads(request.httprequest.data)

        reason = data.get('reason')
        available_date = data.get('available_date')
        note = data.get('note')

        rfq = request.env['purchase.order'].sudo().search([('id', '=', rfq_id), ('partner_id', '=', vendor_id)])
        if not rfq.exists():
            return BaseApiResponse.not_found(message=f"rfq_id wasn't found for this vendor")

        if rfq.state not in ['draft', 'sent']:
            return BaseApiResponse.not_found(message=f"rfq is already processed and it's state cannot be changed")

        blacklist = []
        for rfq_line in rfq.order_line:
            seller_ids = rfq_line.product_id.seller_ids.filtered(
                lambda s: s.product_id.id == rfq_line.product_id.id and s.partner_id.id == vendor_id and s.published
            )
            if seller_ids:
                seller_ids[0].sudo().write({
                    'min_qty': 0,
                })

            rfq_line.sudo().write({
                'available_qty': 0,
                'reason': reason,
                'available_date': available_date,
                'note': note
            })
            blacklist.append({
                'product_id': rfq_line.product_id.id,
                'vendor_id': rfq.partner_id.id,
                'purchase_order_id': rfq.id,
                'sale_order_id' : rfq.sale_order_id.id,
                'reason': reason
            })
        request.env['product.vendor.blacklist'].sudo().create(blacklist)

        try:
            rfq.action_split_rfq()
        except Exception as e:
            return BaseApiResponse.error(message=f"{e}")

        rfq.state = 'cancel'

        return BaseApiResponse.success(data=self.get_order_with_lines_data(rfq_id),message="RFQ was declined successfully")


    # ------------- Utilities -------------
    def get_partner_formated_tags(self, partner_id):
        partner_id = request.env['res.partner'].sudo().browse(partner_id)
        tags = []
        for tag in partner_id.category_id:
            tag_data = {
                'id': tag.id,
                'name': tag.name
            }
            tags.append(tag_data)
        return tags


    def get_vendor_data(self, partner_id):
        partner_id = request.env['res.partner'].sudo().browse(partner_id)
        vendor_data = {
            'id': partner_id.id,
            'mataa_id': partner_id.mataa_id,
            'name': partner_id.name,
            'area': partner_id.city,
            'tags': self.get_partner_formated_tags(partner_id.id),
            'state': 'enabled' if partner_id.active else 'disabled',
            'is_deleted': partner_id.is_deleted,
            'workingHoursStart': partner_id.working_hours_start or "",
            'workingHoursEnd': partner_id.working_hours_end or ""
        }
        return vendor_data

    def get_order_with_lines_data(self, order_id):
        order_id = request.env['purchase.order'].sudo().browse(order_id)
        order_data = {
            'id': order_id.id,
            'create_date': str(order_id.create_date),
            'write_date': str(order_id.write_date),
            'date_order': str(order_id.date_order) if order_id.date_order else None,
            'date_approve': str(order_id.date_approve) if order_id.date_approve else None,
            'state': order_id.state,
            'name': order_id.name,
            'total': order_id.amount_total,
        }
        if order_id.order_line:
            lines_data = []
            for line in order_id.order_line:
                lines_data.append(self.get_order_line_data(line.id))

            order_data['lines'] = lines_data

        return order_data

    def get_order_data(self, order_id):
        order_id = request.env['purchase.order'].sudo().browse(order_id)
        order_data = {
            'id': order_id.id,
            'create_date': str(order_id.create_date),
            'write_date': str(order_id.write_date),
            'date_order': str(order_id.date_order) if order_id.date_order else None,
            'date_approve': str(order_id.date_approve) if order_id.date_approve else None,
            'state': order_id.state,
            'name': order_id.name,
            'total': order_id.amount_total,
        }
        return order_data


    def get_order_line_data(self, order_line_id):
        line = request.env['purchase.order.line'].sudo().browse(order_line_id)

        product_sorted_images = sorted(line.product_id.image_url_ids, key=lambda img: img.sequence)

        line_data = {
            'line_id': line.id,
            'product_id': line.product_id.id,
            'product_mataa_id': line.product_id.mataa_id,

            'create_date': str(line.create_date),
            'write_date': str(line.write_date),
            'date_order': str(line.date_order) if line.date_order else None,
            'date_approve': str(line.date_approve) if line.date_approve else None,

            'product_name': line.product_id.name,
            'product_sku': line.product_id.default_code if line.product_id.default_code else None,
            'product_barcode': line.product_id.barcode if line.product_id.barcode else None,
            'product_additional_barcodes': [barcode.name for barcode in
                                            line.product_id.barcode_ids] if line.product_id.barcode_ids else [],
            'product_main_image': product_sorted_images[0].url if product_sorted_images else None,
            'product_images_gallery': [image.url for image in product_sorted_images] if product_sorted_images else [],
            'product_attributes': [{
                'attribute_id': attr_value.attribute_id.id,
                'attribute_mataa_id': attr_value.attribute_id.mataa_id,
                'attribute_name': attr_value.attribute_id.name,
                'value_id': attr_value.product_attribute_value_id.id,
                'value_mataa_id': attr_value.product_attribute_value_id.mataa_id,
                'value_name': attr_value.product_attribute_value_id.name}
                for attr_value in line.product_id.product_template_attribute_value_ids
            ] if line.product_id.attribute_line_ids else [],
            'description': line.name,
            'quantity': line.product_qty,
            'available_qty': line.available_qty,
            'unit_price': line.price_unit,
        }
        return line_data
