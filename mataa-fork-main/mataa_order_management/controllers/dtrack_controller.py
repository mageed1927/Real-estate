# -*- coding: utf-8 -*-

from odoo import http, _
from odoo.exceptions import UserError
from odoo.http import request
import datetime
import json
from odoo.addons.mataa_base.controllers.common.BaseApiResponse import BaseApiResponse
from odoo.addons.mataa_base.controllers.utility.auth_required import auth_required
from ..utilities.detrack_utility import DetrackUtility
import logging

_logger = logging.getLogger(__name__)

class DTrackController(http.Controller):

    @http.route('/api/blanket-order/<int:bo_id>/close', type='http', auth='public', methods=['POST'], csrf=False)
    def close_bo_request(self, bo_id):
        api_key = request.httprequest.headers.get('X-API-KEY')
        expected_api_key = request.env['ir.config_parameter'].sudo().get_param('mataa_order_management.api_key')
        if api_key != expected_api_key:
            return BaseApiResponse.error(message="Invalid or missing API key.", status=401)
        _logger.info(f"{bo_id}\n"
                     f"{request.httprequest.data}")

        data = json.loads(request.httprequest.data)
        products = data.get('items')

        blanket_order = request.env['purchase.requisition'].sudo().search([('id', '=', bo_id)], limit=1)
        # prevent new lines when driver has arrived
        if data.get("MovementStatus") == "ArrivedAtLocation":
            blanket_order.prevent_line_addition = True
            return BaseApiResponse.success(data=data,message="The movement status has been updated successfully.")


        if not bo_id or not products:
            return BaseApiResponse.not_found()

        if not blanket_order:
            return BaseApiResponse.not_found()

        self._process_product_identifiers(products)

        rfqs = request.env['purchase.order'].sudo().search([
            ('requisition_id', '=', bo_id),
            ('state', 'in', ['draft', 'sent', 'to approve'])
        ])

        if not rfqs:
            return BaseApiResponse.not_found()

        if data['status'] == 'completed':
            # applying rejected quantities
            self._update_rejected_quantities(blanket_order, products)


            pickings_to_be_batched = []

            for rfq in rfqs:
                all_unavailable = True
                for rfq_line in rfq.order_line:
                    if rfq_line.available_qty > 0:
                        all_unavailable = False
                        break

                if all_unavailable:
                    rfq.button_cancel()
                else:
                    rfq.action_confirm()

                picking_type_id = 1  # this is the record id for 'Receipts'

                unique_stock_pickings = request.env['stock.picking'].sudo().search([
                    ('purchase_id', '=', rfq.id),
                    ('state', '=', 'assigned'),
                    ('picking_type_id', '=', picking_type_id)
                ])

                self._update_picking_lines(unique_stock_pickings, products)
                self._handle_pickings_with_no_quantity(unique_stock_pickings, products)

                pickings_to_be_batched.append(unique_stock_pickings)

            self._create_picking_batch(pickings_to_be_batched, bo_id, blanket_order.vendor_id.id)
        elif data['status'] == 'completed_partial':
            # applying rejected quantities
            self._update_rejected_quantities(blanket_order, products)

            pickings_to_be_batched = []
            for rfq in rfqs:
                new_rfq = None
                for rfq_line in rfq.order_line:
                    for product in products:
                        if rfq_line.product_id.default_code == product['sku'] and rfq.name == product['rfq_name']:
                            rfq_line.available_qty -= product['reject_quantity']
                            rfq_line.reason = (rfq_line.reason or "") + f"\n{product['reject_reason']}"

                            if product['reject_quantity'] > 0:
                                new_rfq = self._split_rfq_to_next_vendor(rfq, rfq_line, product, new_rfq)

                rfq.sudo().action_confirm()

                picking_type_id = 1  # this is the record id for 'Receipts'

                unique_stock_pickings = request.env['stock.picking'].sudo().search([
                    ('purchase_id', '=', rfq.id),
                    ('state', '=', 'assigned'),
                    ('picking_type_id', '=', picking_type_id)
                ])

                self._update_picking_lines(unique_stock_pickings, products)
                self._handle_pickings_with_no_quantity(unique_stock_pickings, products)

                pickings_to_be_batched.append(unique_stock_pickings)

            self._create_picking_batch(pickings_to_be_batched, bo_id, blanket_order.vendor_id.id)

        # updating the BO status
        mapped_state = DetrackUtility.get_mapped_state(data['status'])
        if mapped_state:
            blanket_order.state = mapped_state

        # returning the BO
        blanket_order_data = blanket_order.read(['id', 'name', 'vendor_id'])[0]
        return BaseApiResponse.success(data=blanket_order_data, message="The blanket order has been updated successfully.")

    def _process_product_identifiers(self, products):
        """Processes product identifiers for order and RFQ naming."""
        for product in products:
            purchase_order_number = product['purchase_order_number']
            if purchase_order_number:
                parts = [part.strip() for part in purchase_order_number.split('/')]
                product['so_name'] = parts[0].replace("SO ", "") if parts[0] else ""
                product['rfq_name'] = parts[1].replace("RFQ ", "") if len(parts) > 1 else ""

    def _update_rejected_quantities(self, blanket_order, products):
        # applying rejected quantities
        for line in blanket_order.line_ids:
            for product in products:
                if (line.product_id.default_code == product['sku']
                        and line.product_description_variants == product['purchase_order_number']):
                    line.rejected_qty = product['reject_quantity']
                    break

    def _create_picking_batch(self, pickings_to_be_batched, bo_id, vendor_id):
        """Creates a batch for pickings."""
        try:
            batch_vals = {
                'picking_type_id': 1,
                'blanket_order_id': bo_id,
                'vendor_id': vendor_id,
                'picking_ids': [(6, 0, [picking.id for picking in pickings_to_be_batched])],
                'scheduled_date': datetime.datetime.now(),
            }
            request.env['stock.picking.batch'].sudo().create(batch_vals)
        except Exception as e:
            _logger.error(f"Error creating batch: {e}")

    def _update_picking_lines(self, stock_pickings, products):
        # TODO : investigate line duplication with the same products in BO
        for stock_picking_line in stock_pickings.move_ids:
            for product in products:
                if stock_picking_line.product_id.default_code == product['sku'] and stock_picking_line.origin == product['rfq_name']:
                    product_quantity = product['quantity']
                    product_reject_quantity = product['reject_quantity']

                    picked_up_quantity = product_quantity - product_reject_quantity
                    if picked_up_quantity >= stock_picking_line.product_uom_qty:
                        stock_picking_line.quantity = stock_picking_line.product_uom_qty
                        picked_up_quantity -= stock_picking_line.product_uom_qty
                        product['quantity'] -= stock_picking_line.product_uom_qty
                    else:
                        stock_picking_line.quantity = picked_up_quantity
                        product['quantity'] = 0

    def _handle_pickings_with_no_quantity(self, stock_pickings, products):
        # TODO : temporary solution for the problem of confirming RFQ lines with available quantity of 0
        product_skus = [product['sku'] for product in products]
        for stock_picking_line in stock_pickings.move_ids:
            if stock_picking_line.product_id.default_code not in product_skus:
                stock_picking_line.quantity = 0

    def _create_vendor_ticket(self, rfq, rfq_line, vendor):
        if not rfq.company_id.vendor_support_team_id:
            raise UserError(_("Miss configuration: No vendor support team found"))

        ticket_data = {
            'name': 'The vendor declined or partially accepted',
            'description': """Hello Support Team,
                            I have encountered that there's a RFQ line that does not fully accepted by the client.
                            Please advise on how this can be implemented.
                            Thank you""",

            'mataa_customer_id': rfq.sale_order_id.partner_id.id,
            'mataa_vendor_id': vendor.id,
            'mataa_so_id': rfq.sale_order_id.id,
            'mataa_po_id': rfq.id,
            'mataa_product_id': rfq_line.product_id.id,

            'team_id': rfq.company_id.vendor_support_team_id.id,
            'company_id': rfq.company_id.id,
        }

        request.env['helpdesk.ticket'].sudo().create(ticket_data)

    def _create_customer_ticket(self, rfq, rfq_line):
        if not rfq.company_id.customer_support_team_id:
            raise UserError(_("Miss configuration: No customer support team found"))

        ticket_data = {
            'name': 'No Vendor Set for RFQ Line',
            'description': """Hello Support Team,
                                                I have encountered that there's a RFQ line that does not have any vendor set for available quantity.
                                                Please advise on how this can be implemented.
                                                Thank you""",

            'mataa_customer_id': rfq.sale_order_id.partner_id.id,
            'mataa_so_id': rfq.sale_order_id.id,
            'mataa_po_id': rfq.id,
            'mataa_product_id': rfq_line.product_id.id,

            'team_id': rfq.company_id.customer_support_team_id.id,
            'company_id': rfq.company_id.id,
        }

        request.env['helpdesk.ticket'].sudo().create(ticket_data)

    def _get_next_vendor_for_product(self, current_vendor, product, quantity):
        vendors = list(vendor.partner_id for vendor in
                       product.seller_ids.sudo()
                       .filtered(lambda s: s.product_id.id == product.id and s.published)
                       .sorted(key=lambda vendor: vendor.sequence))

        current_vendor_index = vendors.index(current_vendor) if current_vendor in vendors else -1

        next_vendor = None
        for vendor in vendors[current_vendor_index + 1:]:  # Iterate over remaining vendors
            seller_info = product.seller_ids.sudo().filtered(
                lambda s: s.product_id.id == product.id and s.partner_id.id == vendor.id and s.min_qty >= quantity and s.published
            )
            if seller_info:
                next_vendor = vendor
                break  # Stop at the first suitable vendor

        return next_vendor

    def _split_rfq_to_next_vendor(self, rfq, rfq_line, product, new_rfq):
        current_vendor = rfq.partner_id

        self._create_vendor_ticket(rfq, rfq_line, current_vendor)

        request.env['product.vendor.blacklist'].sudo().create({
            'product_id': rfq_line.product_id.id,
            'vendor_id': current_vendor.id,
            'purchase_order_id': rfq.id,
            'sale_order_id': rfq.sale_order_id.id if rfq.sale_order_id else None,
            'reason': rfq_line.reason
        })

        next_vendor = self._get_next_vendor_for_product(current_vendor, rfq_line.product_id, product['reject_quantity'])

        vendor_price = rfq_line.price_unit
        if next_vendor:
            seller_ids = rfq_line.product_id.seller_ids.sudo().filtered(
                lambda s: s.product_id.id == rfq_line.product_id.id and s.partner_id.id == next_vendor.id and s.published
            )
            supplier_info = seller_ids[0]

            vendor_price = supplier_info.price or rfq_line.price_unit

            if not new_rfq or next_vendor.id != new_rfq.partner_id.id:
                new_rfq = rfq.sudo().copy({
                    'order_line': [(5, 0, 0)],  # Clear lines in the new RFQ
                    'sale_order_id': rfq.sale_order_id.id,
                    'origin': rfq.sale_order_id.name,
                    'partner_id': next_vendor.id,
                })

            new_line = rfq_line.sudo().copy({
                'order_id': new_rfq.id,
                'product_qty': product['reject_quantity'],
                'available_qty': 0,
                'product_id': rfq_line.product_id.id,
                'price_unit': vendor_price
            })

            supplier_info.sudo().write({
                'min_qty': supplier_info.min_qty - new_line.product_qty
            })

        else:
            # TODO : review this
            all_rfqs = request.env['purchase.order'].sudo().search(
                [('state', '=', 'draft'), ('sale_order_id', '=', rfq.sale_order_id.id)])

            total_available_qty = rfq_line.available_qty - product['reject_quantity']
            for rfq in all_rfqs:
                for rfq_line in rfq.order_line:
                    if rfq_line.product_id == rfq_line.product_id and rfq_line.available_qty > rfq_line.product_qty:
                        total_available_qty += rfq_line.available_qty - rfq_line.product_qty

            sale_order_line = request.env['sale.order.line'].sudo().search(
                [('product_id', '=', rfq_line.product_id.id),
                 ('order_id', '=', rfq_line.order_id.sale_order_id.id)]
            )

            if total_available_qty > 0:
                sale_order_line.status = 'in_partially_available'
            else:
                sale_order_line.status = 'in_not_available'

            self._create_customer_ticket(rfq, rfq_line)

        return new_rfq
