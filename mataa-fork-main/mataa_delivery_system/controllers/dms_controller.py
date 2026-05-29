# -*- coding: utf-8 -*-

from odoo import http, SUPERUSER_ID
from odoo.http import request
import json
from odoo.addons.mataa_base.controllers.common.BaseApiResponse import BaseApiResponse
import logging
from collections import defaultdict

_logger = logging.getLogger(__name__)


DMS_ENUM_BY_NAME = {
    'undefined': 0,
    'shippingrequest': 1,
    'inwarehouse': 2,
    'ondelivery': 3,
    'ondelevery': 3,
    'delivered': 4,
    'partiallydelivered': 5,
    'failandretry': 6,
    'returnedtosender': 7,
    'returnedtoclient': 8,
    'cancelled': 9
}

def _normalize_dms_status(raw):
    if isinstance(raw, int):
        return raw
    if isinstance(raw, str):
        key = raw.strip().lower().replace(' ', '').replace('_', '').replace('-', '')
        return DMS_ENUM_BY_NAME.get(key)
    return None

DMS_TO_PICKING = {
    0: 'draft',
    1: 'shipping_request',
    2: 'in_warehouse',
    3: 'on_delivery',
    4: 'delivered',
    5: 'partially_delivered',
    6: 'fail_and_retry',
    7: 'out_returned',
    8: 'out_returned',
    9: 'cancelled',
}

# Map canonical integer code to Odoo sale.order DMS status
DMS_TO_SALES = {
    0: 'draft',
    1: 'shipping_request',
    2: 'in_warehouse',
    3: 'on_delivery',
    4: 'delivered',
    5: 'partially_delivered',
    6: 'fail_and_retry',
    7: 'out_returned',
    8: 'out_returned',
    9: 'cancelled',
}

class DMSShipment(http.Controller):

    @http.route('/api/bulk_dms_shipment_status', type='http', auth='public', methods=['POST'], csrf=False)
    def bulk_dms_shipment_status(self):
        try:
            data = json.loads(request.httprequest.data)
        except json.JSONDecodeError:
            return BaseApiResponse.error(message="Invalid JSON data")

        succseeded_shipments = []
        failed_shipments = []
        dms_status_code = data.get('status')
        for shipment_id in data.get('shipmentIds'):

            result = self.update_dms_shipment_status(shipment_id, dms_status_code, shipment_id)
            if result.get('success'):
                succseeded_shipments.append(shipment_id)
            else:
                failed_shipments.append({
                    'shipment_id': shipment_id,
                    'message': result.get('message')
                })
        
        return BaseApiResponse.success(message="Bulk DMS shipment status updated", data={
            'succseeded_shipments': succseeded_shipments,
            'failed_shipments': failed_shipments
        })

    @http.route('/api/dms_shipment_status', type='http', auth='public', methods=['POST'], csrf=False)
    def dms_shpment_status(self):
        try:
            data = json.loads(request.httprequest.data)
        except json.JSONDecodeError:
            return BaseApiResponse.error(message="Invalid JSON data")

        shipment_id = data.get('shipmentId') or data.get('id') or data.get('code')
        raw_status = data.get('status')
        tracking_ref = data.get('trackingRef', shipment_id)

        result = self.update_dms_shipment_status(shipment_id, raw_status, tracking_ref)
        if result.get('success'):
            return BaseApiResponse.success(message=result.get('message'), data=result.get('body'))
        else:
            return BaseApiResponse.error(message=result.get('message'))

    @http.route('/api/dms_return_shipments', type='http', auth='public', methods=['POST'], csrf=False)
    def dms_return_shipments(self):
        try:
            data = json.loads(request.httprequest.data)
        except json.JSONDecodeError:
            return BaseApiResponse.error(message="Invalid JSON data")

        shipments = data.get('shipments') or []
        if not isinstance(shipments, list) or not shipments:
            return BaseApiResponse.error(message="shipments must be a non-empty list")

        succeeded_shipments = []
        failed_shipments = []

        for shipment in shipments:
            result = self._process_dms_return_shipment(shipment)
            if result.get('success'):
                succeeded_shipments.append(result.get('body'))
            else:
                failed_shipments.append({
                    'order_name': shipment.get('order_name'),
                    'message': result.get('message'),
                })

        return BaseApiResponse.success(
            message="DMS return shipments processed",
            data={
                'succeeded_shipments': succeeded_shipments,
                'failed_shipments': failed_shipments,
            }
        )

    def update_dms_shipment_status(self, shipment_id, raw_status, tracking_ref):
        if not shipment_id:
            return {
                'message': "shipmentId is required",
                'success': False
            }
        if raw_status is None:
            return {
                'message': "status is required",
                'success': False
            }

        status_code = _normalize_dms_status(raw_status)
        if status_code is None or status_code not in DMS_TO_PICKING:
            return {
                'message': f"Status '{raw_status}' is not supported",
                'success': False
            }

        _logger.info(f"DMS webhook: shipment_id={shipment_id}, status={raw_status} -> code={status_code}")

        pick = request.env['stock.picking'].sudo().search([
            '&', '|',
            ('dms_shipment_id', '=', shipment_id),
            ('carrier_tracking_ref', '=', tracking_ref),
            ('picking_type_code', '=', 'outgoing')
        ])
        picking_status = None
        for picking in pick:

            if not picking:
                return {
                    'messsage': f"No picking found with DMS shipment ID or tracking: {shipment_id}",
                    'success': False
                }

            try:
                picking_status = DMS_TO_PICKING[status_code]
                picking.dms_shipment_status = picking_status



                sale_order = picking.sale_id or picking.group_id.sale_id
                if sale_order:
                    sale_status = DMS_TO_SALES[status_code]
                    sale_order.dms_shipment_status = sale_status

                if status_code == 2:  # In Warehouse
                    _logger.info(f"DMS status is 'In Warehouse' for picking {picking.name}. Proceeding to validate.")
                    if picking.state not in ('done', 'cancel'):
                        try:
                            picking.with_user(SUPERUSER_ID).button_validate()
                            sale_order.update_mataa_status("packingdone")
                            _logger.info(
                                f"Picking {picking.name} validated successfully based on DMS status 'In Warehouse'.")
                        except Exception as e:
                            _logger.error(f"Failed to validate picking {picking.name} for DMS delivery: {str(e)}")
                            picking.message_post(body=f"Failed to auto-validate picking based on DMS status: {e}")

                elif status_code == 3:  # On Delivery
                    self._handle_on_delivery_status(picking, sale_order)

                elif status_code == 4:  # Delivered
                    self._handle_delivered_status(picking, sale_order)
                # Commented out to prevent updating Mataa Order Status for Return codes 7 and 8.
                # elif status_code == 7:  # Returned
                #     self._handle_returned_to_sender(picking, sale_order)
                # elif status_code == 8:  # Returned
                #     self._handle_returned_to_client(picking, sale_order)
                elif status_code == 5:  # PartiallyDelivered
                    picking.message_post(
                        body="DMS reports: Partially Delivered. Remaining pieces still in transit.",
                        message_type='notification'
                    )

                picking.message_post(
                    body=f"DMS status updated to: {raw_status} ({picking_status})",
                    message_type='notification'
                )

                _logger.info(f"Successfully updated picking {picking.name} with DMS status {raw_status} (code {status_code})")

            except Exception as e:
                _logger.error(f"Error updating DMS shipment status: {str(e)}")
                return {
                    'message': f"Failed to update shipment status: {str(e)}",
                    'shipmentId': shipment_id,
                    'success': False
                }
        
        
        return {
            'body':{'picking_names': pick.mapped('name'), 'odoo_status': picking_status, 'dms_status_code': status_code},
            'shipmentId': shipment_id,
            'message': f"Shipment {shipment_id} status updated",
            'success': True
        }

    def _find_dms_outgoing_pickings(self, order_name=None):
        domain = [('picking_type_code', '=', 'outgoing'), ('state', '=', 'done')]
        pickings = request.env['stock.picking'].with_user(SUPERUSER_ID)

        if order_name:
            return pickings.search(domain + ['|', ('origin', '=', order_name), ('group_id.sale_id.name', '=', order_name)])

        return pickings.browse()

    def _normalize_return_items(self, returned_items):
        normalized_items = {}
        warnings = []
        for item in returned_items or []:
            code = str(item.get('code') or '').strip()
            if not code:
                warnings.append("Skipped a returned item without a product code.")
                continue
            try:
                qty = float(item.get('returnedGoods') or 0.0)
            except (TypeError, ValueError):
                warnings.append(f"Skipped code '{code}' because returnedGoods is invalid.")
                continue
            if qty <= 0:
                warnings.append(f"Skipped code '{code}' because returnedGoods is {qty} and must be greater than 0.")
                continue
            normalized_items[code.casefold()] = normalized_items.get(code.casefold(), 0.0) + qty
        return normalized_items, warnings

    def _get_move_codes(self, move):
        product = move.product_id
        codes = set()
        if product.default_code:
            codes.add(str(product.default_code).strip().casefold())
        if product.barcode:
            codes.add(str(product.barcode).strip().casefold())
        codes.update(str(barcode).casefold() for barcode in product.barcode_ids.mapped('name') if barcode)
        return codes

    def _build_return_candidates(self, pickings):
        candidates_by_code = defaultdict(list)
        returnable_qty_by_move = {}

        for picking in pickings:
            for move in picking.move_ids.filtered(lambda m: m.state != 'cancel'):
                returnable_qty = picking._get_returnable_qty_for_move(move)
                if returnable_qty <= 0:
                    continue
                returnable_qty_by_move[move.id] = returnable_qty
                for code in self._get_move_codes(move):
                    candidates_by_code[code].append({
                        'picking': picking,
                        'move': move,
                        'available_qty': returnable_qty,
                    })

        return candidates_by_code, returnable_qty_by_move

    def _allocate_partial_returns(self, pickings, remaining_items):
        candidates_by_code, _returnable_qty_by_move = self._build_return_candidates(pickings)
        allocations_by_picking = defaultdict(dict)
        warnings = []

        for code, requested_qty in remaining_items.items():
            total_available_qty = sum(candidate['available_qty'] for candidate in candidates_by_code.get(code, []))
            if total_available_qty <= 0:
                warnings.append(f"Skipped code '{code}' because there is no remaining returnable quantity.")
                continue
            if total_available_qty < requested_qty:
                warnings.append(
                    f"Skipped code '{code}' because requested quantity {requested_qty} exceeds remaining returnable quantity {total_available_qty}."
                )
                continue
            qty_to_allocate = requested_qty
            for candidate in candidates_by_code.get(code, []):
                if qty_to_allocate <= 0:
                    break
                available_qty = candidate['available_qty']
                if available_qty <= 0:
                    continue
                allocated_qty = min(available_qty, qty_to_allocate)
                move = candidate['move']
                picking = candidate['picking']
                allocations_by_picking[picking.id][code] = allocations_by_picking[picking.id].get(code, 0.0) + allocated_qty
                candidate['available_qty'] -= allocated_qty
                qty_to_allocate -= allocated_qty
                for sibling_code in self._get_move_codes(move):
                    if sibling_code == code:
                        continue
                    for sibling_candidate in candidates_by_code.get(sibling_code, []):
                        if sibling_candidate['move'].id == move.id:
                            sibling_candidate['available_qty'] = candidate['available_qty']
                            break

        return allocations_by_picking, warnings

    def _process_dms_return_shipment(self, shipment):
        request.update_env(user=SUPERUSER_ID)
        order_name = shipment.get('order_name')
        status_code = _normalize_dms_status(shipment.get('status'))

        if not order_name:
            return {
                'message': "order_name is required",
                'success': False,
            }

        if status_code not in (5, 7, 8):
            return {
                'message': "Only partial-delivery and return statuses are supported for DMS return processing",
                'success': False,
            }

        pickings = self._find_dms_outgoing_pickings(order_name=order_name).sorted(lambda p: (p.date_done or p.write_date or p.create_date, p.id))
        if not pickings:
            return {
                'message': "No done outgoing picking found for the provided order_name",
                'success': False,
            }

        returned_items = shipment.get('returnedItems') or []
        if status_code == 5 and not returned_items:
            return {
                'message': "returnedItems is required for partial-delivery returns",
                'success': False,
            }

        try:
            stock_picking_env = request.env['stock.picking'].with_user(SUPERUSER_ID)
            created_return_ids = []
            warnings = []
            if status_code in (7, 8):
                for picking in pickings:
                    created_return = picking.with_user(SUPERUSER_ID).action_create_dms_customer_return(returned_items=[])
                    if created_return:
                        created_return_ids.extend(created_return.ids)
            else:
                normalized_items, normalize_warnings = self._normalize_return_items(returned_items)
                warnings.extend(normalize_warnings)
                allocations_by_picking, allocation_warnings = self._allocate_partial_returns(
                    pickings,
                    normalized_items,
                )
                warnings.extend(allocation_warnings)
                pickings_by_id = {picking.id: picking for picking in pickings}

                for picking_id, picking_items in allocations_by_picking.items():
                    created_return = pickings_by_id[picking_id].with_user(SUPERUSER_ID).action_create_dms_customer_return(returned_items=[
                        {'code': code, 'returnedGoods': qty}
                        for code, qty in picking_items.items()
                    ])
                    if created_return:
                        created_return_ids.extend(created_return.ids)
        except Exception as e:
            return {
                'message': str(e),
                'success': False,
            }

        created_returns = stock_picking_env.browse(created_return_ids)

        return {
            'body': {
                'order_name': order_name,
                'returned_pickings': created_returns.mapped('name'),
                'processed_outgoing_pickings': pickings.mapped('name'),
                'warnings': warnings,
            },
            'message': "DMS return processed successfully",
            'success': True,
        }

    def _update_sale_order_status(self, sale_order, dms_status):
        if not sale_order:
            return

        so_status_mapping = {
            'CREATED': 'shipped',
            'PICKED_UP': 'shipped',
            'IN_TRANSIT': 'in_transit',
            'OUT_FOR_DELIVERY': 'out_for_delivery',
            'DELIVERED': 'delivered',
            'DELIVERY_FAILED': 'delivery_failed',
            'RETURNED': 'returned',
            'CANCELLED': 'cancelled',
        }

        if dms_status in so_status_mapping:
            sale_order.dms_shipment_status = so_status_mapping[dms_status]

    def _handle_on_delivery_status(self, picking, sale_order):
        if sale_order:
            sale_order.sudo().write({'mata_order_state': 'processing'})
            sale_order.update_mataa_status("processing")


    def _handle_delivered_status(self, picking, sale_order):
        if sale_order:
            sale_order.sudo().write({'mata_order_state': 'completed'})
            sale_order.update_mataa_status("completed")
        if sale_order and hasattr(sale_order, 'close_mataa_order'):
            sale_order.close_mataa_order('fully_delivered')


    def _handle_returned_status(self, picking, sale_order):
        if sale_order and hasattr(sale_order, 'close_mataa_order'):
            sale_order.close_mataa_order('fully_returned')

    def _handle_returned_to_sender(self, picking, sale_order):
        if sale_order:
            sale_order.sudo().write({'mata_order_state': 'wc-on-hold'})
            sale_order.update_mataa_status('wc-on-hold')

    def _handle_returned_to_client(self, picking, sale_order):
        if sale_order:
            sale_order.sudo().write({'mata_order_state': 'failed'})
            sale_order.update_mataa_status('failed')


    @http.route('/api/dms_shipment_info/<string:shipment_id>', type='http', auth='public', methods=['GET'])
    def get_dms_shipment_info(self, shipment_id):
        picking = request.env['stock.picking'].sudo().search([
            ('dms_shipment_id', '=', shipment_id),
            ('picking_type_code', '=', 'outgoing')
        ], limit=1)

        if not picking:
            return BaseApiResponse.error(
                message=f"No shipment found with ID: {shipment_id}"
            )

        data = {
            'shipment_id': picking.dms_shipment_id,
            'picking_name': picking.name,
            'sale_order': picking.sale_id.name if picking.sale_id else None,
            'customer': picking.partner_id.name,
            'status': picking.dms_shipment_status,
            'carrier_tracking_ref': picking.carrier_tracking_ref,
            'scheduled_date': picking.scheduled_date.isoformat() if picking.scheduled_date else None,
            'date_done': picking.date_done.isoformat() if picking.date_done else None,
        }

        return BaseApiResponse.success(
            message="Shipment information retrieved successfully",
            data=data
        )

    @http.route('/api/dms_financial_settlement', type='http', auth='public', methods=['POST'], csrf=False)
    def dms_financial_settlement(self):
        """
        New endpoint to receive financial data (collected price and delegate commission)
        from DMS after delivery.
        """
        try:
            data = json.loads(request.httprequest.data)
        except json.JSONDecodeError:
            return BaseApiResponse.error(message="Invalid JSON data")

        shipment_id = data.get('shipmentId') or data.get('id') or data.get('code')
        tracking_ref = data.get('trackingRef', shipment_id)
        price = data.get('price')
        delegate_value = data.get('delegateValue')

        if not shipment_id:
            return BaseApiResponse.error(message="shipmentId is required")

        if price is None:
            return BaseApiResponse.error(message="price is required")

        if delegate_value is None:
            return BaseApiResponse.error(message="delegateValue is required")

        _logger.info(
            f"DMS webhook (Financial): shipment_id={shipment_id}, price={price}, delegateValue={delegate_value}")

        picking = request.env['stock.picking'].sudo().search([
            '&', '|',
            ('dms_shipment_id', '=', shipment_id),
            ('carrier_tracking_ref', '=', tracking_ref),
            ('picking_type_code', '=', 'outgoing')
        ], limit=1)

        if not picking:
            return BaseApiResponse.error(
                message=f"No picking found with DMS shipment ID or tracking: {shipment_id}"
            )

        try:

            so_id = picking.sale_id or picking.group_id.sale_id
            if so_id:
                so_id.sudo().dms_delegate_commission = float(delegate_value)


            picking.dms_collected_price = float(price)
            picking.dms_delegate_commission = float(delegate_value)


            log_message = (
                f"<strong>DMS Financial Settlement Received:</strong><br/>"
                f"- Collected Price: {price}<br/>"
                f"- Delegate Commission: {delegate_value}"
            )
            picking.message_post(body=log_message)

            _logger.info(f"Successfully updated financial data for picking {picking.name}")

            return BaseApiResponse.success(
                message=f"Financial settlement for {shipment_id} received successfully.",
                data={'picking_name': picking.name}
            )

        except ValueError:
            _logger.error(f"DMS webhook (Financial): Invalid number format for price or delegateValue.")
            return BaseApiResponse.error(message="Invalid data format for 'price' or 'delegateValue'. Must be numbers.")
        except Exception as e:
            _logger.error(f"Error processing DMS financial settlement: {str(e)}")
            return BaseApiResponse.error(
                message=f"Failed to process financial settlement: {str(e)}"
            )

    @http.route('/api/cities', type='http', auth='public', methods=['GET'])
    def get_cities(self):
        
        cities = request.env['mataa.city'].sudo().search([])

        data = []
        for city in cities:
            data.append({
                'id': city.id,
                'name': city.name,
                'code': city.code,
                'camex_city_id': city.camex_city_id,
                'camex_city_name': city.camex_city_name,
                'camex_area_name': city.camex_area_name,
                'camex_total_cost': city.camex_total_cost,
                'line_zone_id': city.line_zone_id,
                'line_subzone_id': city.line_subzone_id,
                'line_total_cost': city.line_total_cost
            })
        return BaseApiResponse.success(
            message="Cities retrieved successfully",
            data=data
        )
