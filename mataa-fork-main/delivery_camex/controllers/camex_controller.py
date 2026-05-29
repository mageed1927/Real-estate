# -*- coding: utf-8 -*-

from odoo import http
from odoo.http import request
import json
from odoo.addons.mataa_base.controllers.common.BaseApiResponse import BaseApiResponse
from odoo.addons.mataa_base.controllers.utility.auth_required import auth_required
import logging
from odoo.tools import Markup

_logger = logging.getLogger(__name__)


class VendorController(http.Controller):
    @http.route('/api/camex_shipment_state', type='http', auth='public', methods=['POST'], csrf=False)
    def update_camex_shipment_state(self):
        _logger.info(f"Webhook Started")
        _logger.info(f"{request.httprequest.data}")
        print("Webhook Started")
        try:
            raw_data_bytes = request.httprequest.data
            data = json.loads(raw_data_bytes)

            print(f"Received Camex webhook request: {raw_data_bytes.decode('utf-8')}")

            secret_key = data.get('secretKey')
            shipment_id = str(data.get('Id'))
        except Exception as e:
            ### FIX: Added logging to see the actual error ###
            _logger.error(f"CRITICAL ERROR in webhook processing: {e}")
            return BaseApiResponse.error(message="Invalid JSON data")

        hardcoded_secret = 'b8c6b543a9934edfb4a33e210c8275b8'
        if secret_key != hardcoded_secret:
            return BaseApiResponse.error(message="Invalid Secret Key")

        out_picking_id = request.env['stock.picking'].sudo().search([
            ('carrier_tracking_ref', '=', shipment_id),
            ('picking_type_code', '=', 'outgoing')], limit=1)

        if not out_picking_id:
            return BaseApiResponse.error(message=f"Shipment with Camex ID {shipment_id} not found.")

        if out_picking_id.state != 'done':
            return BaseApiResponse.error(
                message=f"This picking {out_picking_id.name} is not validated yet. Current state is '{out_picking_id.state}'.")

        # Calling the shipment tracker
        carrier = out_picking_id.carrier_id
        track_data = carrier.camex_track_shipment(shipment_id)

        if not track_data or 'currentState' not in track_data:
            return BaseApiResponse.error(message="Failed to fetch shipment tracking info.")

        try:
            formatted_json = json.dumps(track_data, indent=2)
            chatter_message = f"""
                    <strong>Tracking Data Received from Camex API</strong>
                    <p>The following data was fetched before updating the status:</p>
                    <pre>{formatted_json}</pre>
                    """
            out_picking_id.sudo().message_post(
                ### FIX: Wrap the body in Markup to ensure HTML is rendered ###
                body=Markup(chatter_message),
                subject="Camex Tracking Data Received",
                message_type='notification',
                subtype_xmlid='mail.mt_note'
            )
        except Exception as e:
            _logger.error(f"Failed to post tracking data to chatter: {e}")

        new_state_value = str(track_data['currentState'])
        number_of_items = track_data.get('numberOfItems', 0)
        number_of_returned_items = track_data.get('numberOfReturnedItems', 0)
        price = track_data.get('price', 0)
        delivered_with_price = track_data.get('deliverdWithPrice', 0)

        final_states = ["6", "11", "12", "16"]
        if out_picking_id.camex_shipment_state in final_states:
            statuses = {"6": "Delivered", "11": "Returned", "12": "Money was collected by client", "16": "Canceled"}
            return BaseApiResponse.error(
                message=f"This picking {out_picking_id.name} is already marked as '{statuses.get(out_picking_id.camex_shipment_state)}'")

        out_picking_id.sudo().write({
            'camex_shipment_state': new_state_value,
            'camex_number_of_items': number_of_items,
            'camex_number_of_returned_items': number_of_returned_items,
            'camex_price': price,
            'camex_delivered_with_price': delivered_with_price,
        })

        if out_picking_id.sale_id:
            out_picking_id.sale_id.sudo().write({'camex_shipment_state': new_state_value})

        return BaseApiResponse.success({},
                                       message=f"Shipment {out_picking_id.name} state updated to {new_state_value}")
