# -*- coding: utf-8 -*-

from markupsafe import Markup
from odoo.tools.zeep.helpers import serialize_object

from odoo import api, models, fields, _
from odoo.exceptions import UserError
from odoo.tools import float_repr
from odoo.tools.safe_eval import const_eval

import requests



class ProviderCamex(models.Model):
    _inherit = 'delivery.carrier'

    delivery_type = fields.Selection(selection_add=[
        ('camex', "CAMEX")
    ], ondelete={'camex': lambda recs: recs.write({'delivery_type': 'fixed', 'fixed_price': 0})})

    camex_base_url = fields.Char(string="CAMEX BaseUrl", groups="base.group_system")
    camex_provider_key = fields.Char(string="CAMEX Provider Key", groups="base.group_system")
    camex_client_key = fields.Char(string="CAMEX Client Key", groups="base.group_system")
    camex_store_name = fields.Char(string="Store Name", groups="base.group_system")

    def camex_send_shipping(self, picking):
        # When resending, we need to force a brand-new shipment even if one exists.
        if self.env.context.get('is_resend'):
            picking.write({
                'camex_shipment_id': False,
                'camex_shipment_trace_id': False,
                'carrier_tracking_ref': False,
                'camex_shipment_state': False,
            })

        if picking.camex_shipment_id:
            return [{ 'exact_price': 0,
                      'tracking_number': picking.camex_shipment_id }]

        content, trace_id = self.sudo().camex_create_shipment(picking)
        picking.camex_shipment_id = content
        picking.carrier_tracking_ref = content
        picking.camex_shipment_trace_id = trace_id

        if not isinstance(content, str):
            content = str(content)
        return [{ 'exact_price': 0,
                 'tracking_number': content }]

    def camex_rate_shipment(self, order):
        self.ensure_one()
        if not order.mataa_city_id:
            raise UserError(_('You must select a city first.'))
        vals = {'success': True,
                'price': order.mataa_city_id.camex_total_cost,
                'error_message': False,
                'warning_message': False}

        return vals

    def get_camex_shipment_status(self, picking, status):
        # statuses: out_partially_delivered, out_delivered, out_returned
        self.ensure_one()
        # Todo: Need to understand the camex statuses meaning
        if picking.camex_shipment_state == '6':
            status = "out_delivered"
        elif picking.camex_shipment_state == '11':
            status = "out_returned"
        return status


    def camex_request(self, method, url, headers=None, data=None):
        url = f"{self.sudo().camex_base_url}/{url}"
        if hasattr(requests, method):
            if method == "post":
                response = requests.post(url, headers=headers, data=data)
            else:
                response = getattr(requests, method)(url, headers=headers, data=data)
            if response.status_code == 200:

                response_json = response.json()
                messages = '\n'.join(response_json.get('messages', []))
                res_type = response_json.get('type', 0)

                if res_type == 1:
                    return response_json.get('content'), response_json.get('traceId')
                elif res_type == 2:
                    raise UserError(_(f"Request failed; System Error: \n{messages}"))
                elif res_type == 3:
                    raise UserError(_(f"Request failed; Technical Issue: \n{messages}"))
                else:
                    raise UserError(_(f"Request failed; Unknown Reason: \n{response_json}"))
            else:
                raise UserError(_(f"Request failed with status code: {response.status_code}"))
        else:
            raise UserError(_(f"Request failed; Wrong Method Name: {method}"))

    def camex_login(self):
        self = self.sudo()
        url = f"ApiEndpoints/Login?providerKey={self.camex_provider_key}&clientKey={self.camex_client_key}"
        content, trace_id = self.camex_request('get', url)
        if content and content.get('value'):
            return content['value']
        else:
            raise UserError(_(f"Login failed no content.value: \n{content}"))

    def camex_track_shipment(self, track_no):
        """Track shipment current state from Camex API."""
        headers = {
            "Authorization": f"Bearer {self.camex_login()}"
        }
        url = f"ApiEndpoints/TrackShipment?trackNo={track_no}"
        content, trace_id = self.camex_request('get', url, headers=headers)
        return content

    def camex_get_stores(self):
        headers = {
            "Authorization": f"Bearer {self.camex_login()}"
        }
        url = f"ApiEndpoints/Stores?culture=ar-LY"
        content, trace_id = self.camex_request('get', url, headers=headers)

    def camex_get_cities(self):
        headers = {
            "Authorization": f"Bearer {self.camex_login()}"
        }
        url = f"ApiEndpoints/Cities?culture=ar-LY"
        content, trace_id = self.camex_request('get', url, headers=headers)
        for c in content:
            city_id = self.env['mataa.city'].search([('camex_city_id', '=', c['cityId'])], limit=1)
            if city_id:
                city_id.write({"camex_city_id": c['cityId'],
                               "camex_city_name": c['cityName'],
                               "camex_area_name": c['areaName'],
                               "camex_total_cost": c['totalCost']})
            else:
                city_id.create({"name": c['cityName'],
                                "camex_city_id": c['cityId'],
                               "camex_city_name": c['cityName'],
                               "camex_area_name": c['areaName'],
                               "camex_total_cost": c['totalCost']})


    def camex_create_shipment(self, picking):

        extra_bundled_packs = self._context.get('extra_bundled_packs')
        is_refund = self._context.get('is_refund', False)
        is_resend = bool(self._context.get('is_resend'))
        resend_suffix = '-RESEND' if is_resend else ''

        all_pack_ids = self.env['stock.picking'].browse(extra_bundled_packs) + picking

        sale_id = picking.sale_id
        city_id = sale_id.mataa_city_id
        quantity_mapping = 'move_ids.product_uom_qty' if is_refund else 'move_ids.quantity'

        price = 0
        all_sales = all_pack_ids.mapped('sale_id')
        for sale in all_sales:
            price += sale.get_shipment_price()

        # TODO : add shipping type ShipmentType = 1

        data = {
            "cityId": int(city_id.camex_city_id),
            "noItems": int(sum(all_pack_ids.mapped(quantity_mapping))),
            "price": price,
            "ShipmentType": 1,# allows for customer choice
            "DeliveryCost": 1,
            "productDescrp": (' - '.join(all_pack_ids.mapped('sale_id.name')) + resend_suffix).strip(),
            "storeName": self.camex_store_name,
            "areaName": city_id.camex_area_name,
            "receiverPhone": sale_id.get_customer_phone(),
            "address": "Test Address",
            "notes": ("السماح بالاختيار" + resend_suffix) + " - " + " - ".join(all_sales.mapped('name')) + f"\n{sale_id.get_order_note()}" + "\nرقم إضافي للزبون: "+ sale_id.get_customer_phone_2()
        }

        headers = {
            "Authorization": f"Bearer {self.camex_login()}",
            "Content-Type": "application/json"
        }
        url = "ApiEndpoints/"
        # content, trace_id = self.camex_request('post', url, headers=headers, data=data)


        url = f"{self.camex_base_url}/{url}"
        response = requests.post(url, headers=headers, json=data)

        if response.status_code == 200:
            response_json = response.json()
            messages = '\n'.join(response_json.get('messages', []))
            res_type = response_json.get('type', 0)

            if res_type == 1:
                return response_json.get('content'), response_json.get('traceId')
            elif res_type == 2:
                raise UserError(_(f"Request failed; System Error: \n{messages}"))
            elif res_type == 3:
                raise UserError(_(f"Request failed; Technical Issue: \n{messages}"))
            else:
                raise UserError(_(f"Request failed; Unknown Reason: \n{response_json}"))
        else:
            raise UserError(_(f"Request failed with status code: {response.status_code}"))

    # TODO : this is just a temp fix
    def action_get_camex_cities(self):
        # TODO - To Check: Remove this after finishing testing
        test = self.camex_track_shipment(1881191)
        print(11111111111, test)
        try:
            self.camex_get_cities()
            return {
                'type': 'ir.actions.client',
                'tag': 'reload',
            }
        except Exception as e:
            raise UserError(_("Failed to fetch cities: %s") % e)
