# -*- coding: utf-8 -*-

from odoo import api, models, fields, _
from odoo.exceptions import UserError
import requests
import json
import logging

_logger = logging.getLogger(__name__)

# Payment Codes: 0=Cash, 1=Online/Prepaid, 2=Card on Delivery
DMS_PAYMENT_CODES = {
        'cash': 0,
        'bank': 1,
        'general': 1,
        'CRDOD': 2,
    }

class DeliveryCarrierDMS(models.Model):
    _inherit = 'delivery.carrier'

    delivery_type = fields.Selection(selection_add=[
        ('dms', "DMS")
    ], ondelete={'dms': lambda recs: recs.write({'delivery_type': 'fixed', 'fixed_price': 0})})

    dms_base_url = fields.Char(
        string="DMS Base URL",
        groups="base.group_system",
    )
    dms_api_key = fields.Char(string="DMS API Key", groups="base.group_system")
    dms_sender_name = fields.Char(string="Default Sender Name", groups="base.group_system")
    dms_payment_type_code = fields.Integer(string="Default Payment Type Code", default=1, groups="base.group_system")
    dms_openable_code = fields.Char(string="Default Openable Code", default="Y", groups="base.group_system")

    def dms_send_shipping(self, picking):
        # bundled_sale_orders = self.env.context.get('bundled_sale_orders')
        so = picking.sale_id
        bundled_sale_orders = so.mataa_bundle_id.mataa_bundled_so_ids
        dms_shipment_id = None
        dms_shipment_ids = None

        if bundled_sale_orders:
            dms_shipment_ids = self.sudo().dms_create_combined_shipment(picking, bundled_sale_orders)
            picking.carrier_tracking_ref = dms_shipment_ids
            if not isinstance(dms_shipment_ids, str):
                dms_shipment_ids = str(dms_shipment_ids)
        else:
            dms_shipment_id = self.sudo().dms_create_shipment(picking)
            picking.carrier_tracking_ref = dms_shipment_id

            if not isinstance(dms_shipment_id, str):
                dms_shipment_id = str(dms_shipment_id)

        return [{
            'exact_price': 0,
            'tracking_number': dms_shipment_id or dms_shipment_ids
        }]

    def dms_create_combined_shipment(self, picking, bundled_sale_orders):
        self.ensure_one()

        is_resend = bool(self.env.context.get('is_resend'))
        resend_suffix = '-RESEND' if is_resend else ''

        all_so_names = []
        all_products = []
        shipment_price = 0.0
        total_order_amount = 0.0
        total_quantity = 0

        combined_order_lines = []
        payment_type_codes = set()

        for sale_order in bundled_sale_orders:
            all_so_names.append(sale_order.name)

            for line in sale_order.order_line:
                if line.product_id.type != 'service':
                    all_products.append(line.product_id.name)
                    total_quantity += line.product_uom_qty
                    combined_order_lines.append({
                        'product_id': line.product_id.id,
                        'product_name': line.product_id.name,
                        'product_code': line.product_id.default_code,
                        'productBarcode': line.product_id.barcode or "",
                        'quantity': line.product_uom_qty,
                        'price_unit': line.price_unit,
                        'price_subtotal': line.price_subtotal,
                        'product_image': line.so_line_main_image if line.so_line_main_image else None,
                    })

            shipment_price += sale_order.get_shipment_price() if hasattr(sale_order, 'get_shipment_price') else sale_order.amount_total
            total_order_amount += sale_order.amount_total

            customer_phone = sale_order.get_customer_phone() if hasattr(sale_order,
                                                                        'get_customer_phone') else sale_order.partner_id.phone
            customer_mobile = sale_order.get_customer_phone_2() if hasattr(sale_order,
                                                                           'get_customer_phone_2') else sale_order.partner_id.mobile

            if customer_phone and not customer_phone.startswith("+"):
                customer_phone = f"{customer_phone}"
            if customer_mobile and not customer_mobile.startswith("+"):
                customer_mobile = f"{customer_mobile}"
            
            if hasattr(sale_order, 'mataa_payment_ids') and sale_order.mataa_payment_ids:
                for payment in sale_order.mataa_payment_ids:
                    if payment.code:
                        journal = self.env['account.journal'].search([('code', '=', payment.code)])
                        code_type = journal.type
                        mapped_code = DMS_PAYMENT_CODES.get(code_type)
                        if code_type == 'bank' and not journal.e_payment_journal:
                            mapped_code = DMS_PAYMENT_CODES.get('CRDOD')
                        payment_type_codes.add(mapped_code)
        payment_methods = list(payment_type_codes)

        recipient_phone_2 = picking.sale_id.mata_billing_phone if hasattr(picking.sale_id, 'mata_billing_phone') else ""

        delivery_fees = 0.0
        for sale_order in bundled_sale_orders:
            for line in sale_order.order_line:
                if line.product_id.name == 'DMS Delivery':
                    delivery_fees += line.price_total

        combined_shipment_data = {
            "code": f"{', '.join(all_so_names)}{resend_suffix}",
            "cityCode": picking.sale_id.mataa_city_id.code,
            "senderName": self.dms_sender_name or "Default Sender",
            "recipientName": picking.partner_id.name,
            "recipientPhone": customer_phone or "No phone provided",
            "recipientPhone2": recipient_phone_2 or "",
            "recipientMobile": customer_mobile or "No mobile, provided",
            "recipientAddress": picking.sale_id.mata_shipping_address_1 if hasattr(picking.sale_id,
                                                                                  'mata_shipping_address_1') else picking.sale_id.partner_id.street or "",
            "recipientZoneId": picking.sale_id.mataa_city_id.line_zone_id or "",
            "recipientSubzoneId": picking.sale_id.mataa_city_id.line_subzone_id or "",
            "piecesCount": int(total_quantity),
            "deliveryFees": delivery_fees,
            "price": shipment_price,
            "totalOrderAmount": total_order_amount,
            "paymentTypeCode": self.dms_payment_type_code,
            "openableCode": self.dms_openable_code,
            "notes": f"Bundle Order: {', '.join(all_so_names)}",
            "description": f"Combined shipment for bundled sale orders: {', '.join(all_so_names)}",
            "orderLines": combined_order_lines,
            "paymentMethods": payment_methods,
            "so_tags": ", ".join(tag for order in bundled_sale_orders for tag in order.mataa_tag_ids.mapped('name')),
        }

        try:
            response = self._send_to_dms_api(combined_shipment_data)
            return response
        except Exception as e:
            raise UserError(_('Error creating DMS shipment: %s') % str(e))

    def _send_to_dms_api(self, shipment_data):
        headers = {
            'Content-Type': 'application/json',
        }

        url = f"{self.dms_base_url}/api/v1/Shipment/createFromOdoo"

        response = requests.post(url, headers=headers, data=json.dumps(shipment_data), timeout=30)

        if response.status_code != 200:
            raise UserError(_('Failed to create DMS shipment. API returned status code: %s') % response.status_code)

        response_data = response.json()

        shipment_id = response_data.get('id') or response_data.get('shipmentId') or response_data.get('tracking_number')
        if not shipment_id:
            raise UserError(_('DMS API did not return a valid shipment ID.'))

        return shipment_id

    def dms_rate_shipment(self, order):
        self.ensure_one()
        if not order.mataa_city_id:
            raise UserError(_('You must select a city first.'))

        vals = {
            'success': True,
            'price': order.mataa_city_id.line_total_cost,
            'error_message': False,
            'warning_message': False
        }
        return vals

    def dms_create_shipment(self, picking):
        self.ensure_one()

        sale_order = picking.sale_id or picking.group_id.sale_id
        if not sale_order:
            raise UserError(_('No sale order found for this picking.'))

        is_resend = bool(self.env.context.get('shipment_resend') or self.env.context.get('is_resend'))
        resend_suffix = '-RESEND' if is_resend else ''

        if not sale_order.mataa_city_id:
            raise UserError(_('City is required for DMS shipment creation.'))
        if not sale_order.mataa_city_id.line_zone_id:
            raise UserError(_('Zone ID is not configured for city: %s') % sale_order.mataa_city_id.name)
        if not sale_order.mataa_city_id.line_subzone_id:
            raise UserError(_('Subzone ID is not configured for city: %s') % sale_order.mataa_city_id.name)

        customer_phone = sale_order.get_customer_phone() if hasattr(sale_order,
                                                                    'get_customer_phone') else sale_order.partner_id.phone
        customer_mobile = sale_order.get_customer_phone_2() if hasattr(sale_order,
                                                                       'get_customer_phone_2') else sale_order.partner_id.mobile

        recipient_phone_2 = sale_order.mata_billing_phone if hasattr(sale_order, 'mata_billing_phone') else ""

        if customer_phone and not customer_phone.startswith("+"):
            customer_phone = f"{customer_phone}"
        if customer_mobile and not customer_mobile.startswith("+"):
            customer_mobile = f"{customer_mobile}"

        pieces_count = int(sum(picking.move_ids.mapped('quantity')))

        shipment_price = sale_order.get_shipment_price() if hasattr(sale_order,
                                                                    'get_shipment_price') else sale_order.amount_total

        total_order_amount = sale_order.amount_total

        delivery_fees = sum(
            line.price_total for line in sale_order.order_line if line.product_id.name == 'DMS Delivery')

        order_notes = sale_order.mataa_customer_note if hasattr(sale_order, 'mataa_customer_note') else sale_order.note or ""

        order_lines_data = [
            {
                'product_id': line.product_id.id,
                'product_name': line.product_id.name,
                'product_code': line.product_id.default_code,
                'productBarcode': line.product_id.barcode or "",
                'quantity': line.product_uom_qty,
                'price_unit': line.price_unit,
                'price_subtotal': line.price_subtotal,
                'product_image': line.so_line_main_image if line.so_line_main_image else None,
            }
            for line in sale_order.order_line if line.product_id.type != 'service'
        ]

        payment_type_codes = set()
        if hasattr(sale_order, 'mataa_payment_ids') and sale_order.mataa_payment_ids:
            for payment in sale_order.mataa_payment_ids:
                if payment.code:
                    journal = self.env['account.journal'].search([('code', '=', payment.code)])
                    code_type = journal.type
                    mapped_code = DMS_PAYMENT_CODES.get(code_type)
                    if code_type == "bank" and not journal.e_payment_journal:
                        mapped_code = DMS_PAYMENT_CODES.get('CRDOD')
                    payment_type_codes.add(mapped_code)

        payment_methods = list(payment_type_codes)

        shipment_data = {
            "code": f"{sale_order.name}{resend_suffix}",
            'cityCode': sale_order.mataa_city_id.code,
            "model": "Odoo",
            "senderName": self.dms_sender_name or "Default Sender",
            "recipientName": sale_order.partner_id.name,
            "recipientPhone": customer_phone or "",
            "recipientPhone2": recipient_phone_2 or "",
            "recipientMobile": customer_mobile or "",
            "recipientAddress": str(sale_order.mata_shipping_address_1 or sale_order.partner_id.street or "No Address Provided"),
            "recipientZoneId": sale_order.mataa_city_id.line_zone_id,
            "recipientSubzoneId": sale_order.mataa_city_id.line_subzone_id,
            "piecesCount": pieces_count,
            "deliveryFees": delivery_fees,
            "price": shipment_price,
            "totalOrderAmount": total_order_amount,
            "paymentTypeCode": self.dms_payment_type_code,
            "openableCode": self.dms_openable_code,
            "notes": f"{sale_order.name}\n{order_notes}",
            "description": f"Outgoing Shipment - {sale_order.name}",
            "orderLines": order_lines_data,
            "paymentMethods": payment_methods,
            "so_tags": ", ".join(sale_order.mataa_tag_ids.mapped('name')),        }

        headers = {
            'Content-Type': 'application/json'
        }

        if self.dms_api_key:
            headers['x-api-key'] = self.dms_api_key

        url = f"{self.dms_base_url}/api/v1/Shipment/createFromOdoo"

        try:
            response_data = None

            _logger.info(f"Creating DMS shipment for picking {picking.name} with data: {shipment_data}")

            response = requests.post(
                url,
                headers=headers,
                data=json.dumps(shipment_data),
                timeout=30
            )

            _logger.info(f"DMS API Response Body: {response.text}")
            response_data = response.json()
            response.raise_for_status()

            shipment_id = None
            if isinstance(response_data, dict):
                shipment_id = (response_data.get('id') or
                               response_data.get('shipmentId') or
                               response_data.get('tracking_number') or
                               response_data.get('code'))
            elif isinstance(response_data, str):
                shipment_id = response_data
            elif isinstance(response_data, (int, float)):
                shipment_id = str(response_data)

            if not shipment_id:
                raise UserError(_('DMS API did not return a valid shipment ID. Response: %s') % response_data)

            _logger.info(f"DMS shipment created successfully with ID: {shipment_id}")
            return shipment_id

        except requests.exceptions.RequestException as e:
            try:
                error = response_data['errors']
            except Exception:
                try:
                    error = response_data['message']
                except Exception:
                    if response_data:
                        error = response_data
                    else:
                        error = e
            _logger.error(f"DMS API request failed: {str(error)}")
            raise UserError(_('Failed to create DMS shipment: %s') % str(error))
        except json.JSONDecodeError as e:
            _logger.error(f"Failed to parse DMS API response: {str(e)}")
            raise UserError(_('Invalid response from DMS API: %s') % str(e))
        except Exception as e:
            _logger.error(f"Unexpected error creating DMS shipment: {str(e)}")
            raise UserError(_('Error creating DMS shipment: %s') % str(e))

    def get_dms_shipment_status(self, picking, status):
        self.ensure_one()
        DMS_ENUM_BY_NAME = {
            'undefined': 0,
            'shippingrequest': 1,
            'inwarehouse': 2,
            'ondelivery': 3,
            'ondelevery': 3,  # Alias
            'delivered': 4,
            'deleverd': 4,  # Alias
            'partiallydelivered': 5,
            'failandretry': 6,
            'returnedtosender': 7,
            'returnedtoclient': 8,
            'cancelled': 9
        }
        def _norm(raw):
            if isinstance(raw, int):
                return raw
            if isinstance(raw, str):
                k = raw.strip().lower().replace(' ', '').replace('_', '').replace('-', '')
                return DMS_ENUM_BY_NAME.get(k)
            return None

        picking_map = {
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
        code = _norm(status)
        return picking_map.get(code, picking.dms_shipment_status or 'draft')


    def dms_update_shipment(self, picking):
        """
        Update the DMS shipment for the given picking using the linked sale order.
        Builds the payload from picking.sale_id (same style as dms_create_shipment).
        If the sale order is part of a bundle, delegates to dms_update_combined_shipment.
        """
        self.ensure_one()
        picking.ensure_one()

        order = picking.sale_id or picking.group_id.sale_id
        if not order:
            raise UserError(_('No sale order found for this picking.'))

        bundled_sale_orders = order.mataa_bundle_id.mataa_bundled_so_ids if order.mataa_bundle_id else False
        if bundled_sale_orders:
            return self.sudo().dms_update_combined_shipment(picking, bundled_sale_orders)

        if not order.mataa_city_id:
            raise UserError(_('City is required for DMS shipment update.'))
        if not order.mataa_city_id.line_zone_id:
            raise UserError(_('Zone ID is not configured for city: %s') % order.mataa_city_id.name)
        if not order.mataa_city_id.line_subzone_id:
            raise UserError(_('Subzone ID is not configured for city: %s') % order.mataa_city_id.name)

        customer_phone = order.get_customer_phone() if hasattr(order, 'get_customer_phone') else order.partner_id.phone
        customer_mobile = order.get_customer_phone_2() if hasattr(order, 'get_customer_phone_2') else order.partner_id.mobile
        recipient_phone_2 = order.mata_billing_phone if hasattr(order, 'mata_billing_phone') else ''

        if customer_phone and not customer_phone.startswith('+'):
            customer_phone = f'{customer_phone}'
        if customer_mobile and not customer_mobile.startswith('+'):
            customer_mobile = f'{customer_mobile}'

        shipment_price = order.get_shipment_price() if hasattr(order, 'get_shipment_price') else order.amount_total
        total_order_amount = order.amount_total
        delivery_fees = sum(
            line.price_total for line in order.order_line if line.product_id.name == 'DMS Delivery'
        )
        order_notes = order.mataa_customer_note if hasattr(order, 'mataa_customer_note') else order.note or ''
        pieces_count = int(sum(picking.move_ids.mapped('quantity')))

        payment_type_codes = set()
        if hasattr(order, 'mataa_payment_ids') and order.mataa_payment_ids:
            for payment in order.mataa_payment_ids:
                if payment.code:
                    journal = self.env['account.journal'].search([('code', '=', payment.code)])
                    code_type = journal.type
                    mapped_code = DMS_PAYMENT_CODES.get(code_type)
                    if code_type == 'bank' and not journal.e_payment_journal:
                        mapped_code = DMS_PAYMENT_CODES.get('CRDOD')
                    payment_type_codes.add(mapped_code)
        payment_methods = list(payment_type_codes)

        order_lines_data = [
            {
                'product_id': line.product_id.id,
                'product_name': line.product_id.name,
                'product_code': line.product_id.default_code,
                'productBarcode': line.product_id.barcode or "",
                'quantity': line.product_uom_qty,
                'price_unit': line.price_unit,
                'price_subtotal': line.price_subtotal,
                'product_image': line.so_line_main_image if line.so_line_main_image else None,
            }
            for line in order.order_line if line.product_id.type != 'service'
        ]

        shipment_data = {
            'shipmentId': picking.carrier_tracking_ref,
            'code': order.name,
            'cityCode': order.mataa_city_id.code,
            'model': 'Odoo',
            'senderName': self.dms_sender_name or 'Default Sender',
            "recipientName": order.partner_id.name,
            'recipientPhone': customer_phone or '',
            'recipientPhone2': recipient_phone_2 or '',
            'recipientMobile': customer_mobile or '',
            'recipientAddress': str(order.mata_shipping_address_1 or order.partner_id.street or 'No Address Provided'),
            'recipientZoneId': order.mataa_city_id.line_zone_id,
            'recipientSubzoneId': order.mataa_city_id.line_subzone_id,
            'deliveryFees': delivery_fees,
            "piecesCount": pieces_count,
            'price': shipment_price,
            'totalOrderAmount': total_order_amount,
            'paymentTypeCode': self.dms_payment_type_code,
            'openableCode': self.dms_openable_code,
            'description': f'Outgoing Shipment - {order.name}',
            "orderLines": order_lines_data,
            'notes': f'{order.name}\n{order_notes}',
            'paymentMethods': payment_methods,
            'so_tags': ", ".join(order.mataa_tag_ids.mapped('name')),
        }

        headers = {'Content-Type': 'application/json'}
        if self.dms_api_key:
            headers['x-api-key'] = self.dms_api_key

        url = f'{self.dms_base_url}/api/v1/Shipment/UpdateFromOdoo'
        _logger.info('Updating DMS shipment %s for order %s', picking.carrier_tracking_ref, order.name)

        try:
            response = requests.put(
                url,
                headers=headers,
                data=json.dumps(shipment_data),
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            _logger.exception('Failed to update DMS shipment %s', picking.carrier_tracking_ref)
            raise UserError(_('Failed to update DMS shipment: %s') % str(e))

    def dms_update_combined_shipment(self, picking, bundled_sale_orders):

        self.ensure_one()
        picking.ensure_one()

        all_so_names = []
        all_products = []
        shipment_price = 0.0
        total_order_amount = 0.0
        total_quantity = 0
        combined_order_lines = []
        payment_type_codes = set()

        for sale_order in bundled_sale_orders:
            all_so_names.append(sale_order.name)

            for line in sale_order.order_line:
                if line.product_id.type != 'service':
                    all_products.append(line.product_id.name)
                    total_quantity += line.product_uom_qty
                    combined_order_lines.append({
                        'product_id': line.product_id.id,
                        'product_name': line.product_id.name,
                        'product_code': line.product_id.default_code,
                        'productBarcode': line.product_id.barcode or "",
                        'quantity': line.product_uom_qty,
                        'price_unit': line.price_unit,
                        'price_subtotal': line.price_subtotal,
                        'product_image': line.so_line_main_image if line.so_line_main_image else None,
                    })

            shipment_price += sale_order.get_shipment_price() if hasattr(sale_order, 'get_shipment_price') else sale_order.amount_total
            total_order_amount += sale_order.amount_total

            customer_phone = sale_order.get_customer_phone() if hasattr(sale_order,
                                                                        'get_customer_phone') else sale_order.partner_id.phone
            customer_mobile = sale_order.get_customer_phone_2() if hasattr(sale_order,
                                                                           'get_customer_phone_2') else sale_order.partner_id.mobile

            if customer_phone and not customer_phone.startswith("+"):
                customer_phone = f"{customer_phone}"
            if customer_mobile and not customer_mobile.startswith("+"):
                customer_mobile = f"{customer_mobile}"

            if hasattr(sale_order, 'mataa_payment_ids') and sale_order.mataa_payment_ids:
                for payment in sale_order.mataa_payment_ids:
                    if payment.code:
                        journal = self.env['account.journal'].search([('code', '=', payment.code)])
                        code_type = journal.type
                        mapped_code = DMS_PAYMENT_CODES.get(code_type)
                        if code_type == 'bank' and not journal.e_payment_journal:
                            mapped_code = DMS_PAYMENT_CODES.get('CRDOD')
                        payment_type_codes.add(mapped_code)
        payment_methods = list(payment_type_codes)

        recipient_phone_2 = picking.sale_id.mata_billing_phone if hasattr(picking.sale_id, 'mata_billing_phone') else ""

        delivery_fees = 0.0
        for sale_order in bundled_sale_orders:
            for line in sale_order.order_line:
                if line.product_id.name == 'DMS Delivery':
                    delivery_fees += line.price_total

        shipment_data = {
            "shipmentId": picking.carrier_tracking_ref,
            "code": f"{', '.join(all_so_names)}",
            "cityCode": picking.sale_id.mataa_city_id.code,
            "senderName": self.dms_sender_name or "Default Sender",
            "recipientName": picking.partner_id.name,
            "recipientPhone": customer_phone or "No phone provided",
            "recipientPhone2": recipient_phone_2 or "",
            "recipientMobile": customer_mobile or "No mobile, provided",
            "recipientAddress": picking.sale_id.mata_shipping_address_1 if hasattr(picking.sale_id,
                                                                                  'mata_shipping_address_1') else picking.sale_id.partner_id.street or "",
            "recipientZoneId": picking.sale_id.mataa_city_id.line_zone_id or "",
            "recipientSubzoneId": picking.sale_id.mataa_city_id.line_subzone_id or "",
            "piecesCount": int(total_quantity),
            "deliveryFees": delivery_fees,
            "price": shipment_price,
            "totalOrderAmount": total_order_amount,
            "paymentTypeCode": self.dms_payment_type_code,
            "openableCode": self.dms_openable_code,
            "notes": f"Bundle Order: {', '.join(all_so_names)}",
            "description": f"Combined shipment for bundled sale orders: {', '.join(all_so_names)}",
            "orderLines": combined_order_lines,
            "paymentMethods": payment_methods,
            "so_tags": ", ".join(tag for order in bundled_sale_orders for tag in order.mataa_tag_ids.mapped('name')),
        }

        headers = {'Content-Type': 'application/json'}
        if self.dms_api_key:
            headers['x-api-key'] = self.dms_api_key

        url = f'{self.dms_base_url}/api/v1/Shipment/UpdateFromOdoo'
        _logger.info('Updating combined DMS shipment %s for bundled orders %s',
                     picking.carrier_tracking_ref, ', '.join(all_so_names))

        try:
            response = requests.put(
                url,
                headers=headers,
                data=json.dumps(shipment_data),
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            _logger.exception('Failed to update combined DMS shipment %s', picking.carrier_tracking_ref)
            raise UserError(_('Failed to update combined DMS shipment: %s') % str(e))