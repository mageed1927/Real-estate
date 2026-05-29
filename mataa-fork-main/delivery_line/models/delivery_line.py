# -*- coding: utf-8 -*-

from odoo import api, models, fields, _
from odoo.exceptions import UserError

import requests



class ProviderLine(models.Model):
    _inherit = 'delivery.carrier'

    delivery_type = fields.Selection(selection_add=[
        ('line', "Line")
    ], ondelete={'line': lambda recs: recs.write({'delivery_type': 'fixed', 'fixed_price': 0})})

    line_base_url = fields.Char(string="Line BaseUrl", groups="base.group_system")
    line_username = fields.Char(string="Line Username", groups="base.group_system")
    line_password = fields.Char(string="Line Password", groups="base.group_system")


    def line_send_shipping(self, picking):
        if picking.line_shipment_id:
            return [{ 'exact_price': 0,
                      'tracking_number': picking.line_shipment_id }]

        line_shipment_id = self.sudo().line_create_shipment(picking)
        picking.line_shipment_id = line_shipment_id
        picking.carrier_tracking_ref = line_shipment_id

        if not isinstance(line_shipment_id, str):
            line_shipment_id = str(line_shipment_id)
        return [{ 'exact_price': 0,
                  'tracking_number': line_shipment_id }]

    def line_rate_shipment(self, order):
        self.ensure_one()
        if not order.mataa_city_id:
            raise UserError(_('You must select a city first.'))
        vals = {'success': True,
                'price': order.mataa_city_id.line_total_cost,
                'error_message': False,
                'warning_message': False}

        return vals

    def get_line_shipment_status(self, picking, status):
        # statuses: out_partially_delivered, out_delivered, out_returned
        self.ensure_one()
        # Todo: Need to understand the line statuses meaning
        if picking.line_shipment_sate == '6':
            status = "out_delivered"
        elif picking.line_shipment_sate == '11':
            status = "out_returned"
        return status

    def line_login(self):
        self = self.sudo()

        url = self.line_base_url

        username = self.line_username
        password = self.line_password

        query = """
        mutation ($input: LoginInput!) {
          login(input: $input) {
            user {
              id
              username
              active
              isSuper
            }
            token
          }
        }
        """

        variables = {
            "input": {
                "username": username,
                "password": password,
                "rememberMe": True,
                "fcmToken": "fcmToken"
            }
        }

        # Prepare request payload
        payload = {
            "query": query,
            "variables": variables
        }

        # Make the request with basic authentication
        response = requests.post(
            url,
            json=payload,
            auth=(username, password)  # Basic Auth
        )

        json_response = response.json()
        if json_response.get('data', False) and json_response['data'].get('login', False) and json_response['data']['login'].get('token', False):
            return json_response['data']['login']['token']
        elif json_response.get('errors', False):
            raise UserError(_(f"Login failed: \n{json_response.get('errors')}"))
        else:
            raise UserError(_(f"Login failed: \n{json_response}"))

    def line_create_shipment(self, picking):

        token = self.line_login()


        sender_id = self.env['ir.config_parameter'].sudo().get_param('delivery_line.default_sender_id')
        sender = self.env['res.partner'].search([('id', '=', sender_id)])
        if not sender:
            raise UserError(_('Please configure a sender contact in either the delivery carrier or the Line settings.'))

        mutation = """
        mutation ($input: ShipmentInput!) {
            saveShipment(input: $input) {
                id
                date
                code
                recipientName
                description
                piecesCount
                recipientAddress
                amount
                totalAmount
                allDueFees
                inWarehouse
                recipientZone {
                    id
                    name
                }
                customer {
                    id
                    name
                    code
                }
                recipientSubzone {
                    id
                    name
                }
            }
        }
        """

        # Set up the headers and payload for the request
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }

        sale_id = picking.sale_id

        extra_bundled_packs = self._context.get('extra_bundled_packs')
        is_refund = self._context.get('is_refund', False)

        all_pack_ids = self.env['stock.picking'].browse(extra_bundled_packs) + picking

        customer_phone = sale_id.get_customer_phone()
        customer_phone = customer_phone if customer_phone.startswith("+") else f"+{customer_phone}"

        customer_alternative_phone = sale_id.get_customer_phone_2()
        customer_alternative_phone = customer_alternative_phone if customer_alternative_phone.startswith("+") else f"+{customer_alternative_phone}"

        quantity_mapping = 'move_ids.product_uom_qty' if is_refund else 'move_ids.quantity'

        price = 0
        all_sales = all_pack_ids.mapped('sale_id')
        for sale in all_sales:
            price += sale.get_shipment_price()

        input_data = {
            'code': " - ".join(all_sales.mapped('name')),
            'notes': ' - '.join(all_pack_ids.mapped('sale_id.name')) + f"\n{sale_id.get_order_note()}",
            'paymentTypeCode': 'COLC',
            'priceTypeCode': 'INCLD',

            'recipientName': sale_id.partner_id.name,
            'recipientPhone': customer_phone,
            'recipientMobile': customer_alternative_phone,
            'recipientZoneId': sale_id.mataa_city_id.line_zone_id,
            'recipientSubzoneId': sale_id.mataa_city_id.line_subzone_id,
            'recipientAddress': sale_id.mata_shipping_address_1 or "test",

            'senderName': sender.name,
            'senderPhone': sender.phone,
            'senderMobile': sender.mobile,
            'senderZoneId': 1,
            'senderSubzoneId': 333,
            'senderAddress': 'Mataa Base',

            'description': 'Incoming Shipment(Refund)' if is_refund else 'Outgoing Shipment',
            'weight': 1.0,
            'piecesCount': int(sum(all_pack_ids.mapped(quantity_mapping))),
            'price': price,
            'typeCode': 'FDP',
            'openableCode': 'Y',
            'serviceId': 1,
            'size': {
                'length': 0,
                'height': 0,
                'width': 0
            }
        }



        payload = {
            'query': mutation,
            'variables': {
                'input': input_data
            }
        }

        # Send the POST request to the GraphQL endpoint
        response = requests.post(self.line_base_url, headers=headers, json=payload)

        json_response = response.json()  # Parse JSON response

        if json_response.get('data', False) and json_response['data'].get('saveShipment', False) and json_response['data']['saveShipment'].get('id', False):
            return json_response['data']['saveShipment']['id']
        elif json_response.get('errors', False):
            raise UserError(_(f"Error: \n{json_response.get('errors')}"))
        else:
            raise UserError(_(f"Issue: \n{json_response}"))
