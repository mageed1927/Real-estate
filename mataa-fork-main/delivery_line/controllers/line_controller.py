# -*- coding: utf-8 -*-

from odoo import http, SUPERUSER_ID
from odoo.http import request
import json
from odoo.addons.mataa_base.controllers.common.BaseApiResponse import BaseApiResponse
from odoo.addons.mataa_base.controllers.utility.auth_required import auth_required
import logging

_logger = logging.getLogger(__name__)


class LineShipment(http.Controller):

    @http.route('/api/line_shipment_state', type='http', auth='public', methods=['POST'], csrf=False)
    def update_line_shipment_state(self):
        data = json.loads(request.httprequest.data)
        # secret_key = request.httprequest.headers.get('x-api-key')
        # if secret_key != request.env['ir.config_parameter'].sudo().get_param('delivery_line.line_secret_key'):
        #     return BaseApiResponse.error(message="Invalid API Key")

        shipment_id = data.get('shipmentId', False)
        new_status = data.get('shipmentStatusCode', False)
        return_pieces = data.get('return_pieces', 0)
        shipping_type = data.get('shippingRequestType', False)

        _logger.info(f"shipment data is (state:{new_status} , shipment_id:{shipment_id})")
        out_picking = request.env['stock.picking'].sudo().search([
            ('carrier_tracking_ref', '=', shipment_id),
            ('picking_type_code', '=', 'outgoing')
        ], limit=1)
        allowed_states = [
            'PKR', 'PKM', 'PKD', 'RJCT', 'RITS', 'OTD', 'DTR', 'DEX', 'HTR',
            'RTS', 'OTR', 'RTRN', 'BMR', 'BMT', 'PKH', 'PRP', 'STD', 'RCV', 'PRPD'
        ]

        if new_status not in allowed_states:
            return BaseApiResponse.error(message=f"status {new_status} isn't allowed on odoo")

        def update_status(picking, state):
            # picking.group_id.sale_id.sudo().write({'delivery_line_status': state})
            sale_order = picking.sale_id or picking.group_id.sale_id
            if sale_order:
                sale_order.sudo().write({'delivery_line_status': state})

        if new_status == "RITS":
            if out_picking.state in ['done', 'cancel']:
                return BaseApiResponse.error(
                    message=f"Shipment {shipment_id} was already validated or canceled in Odoo")
            _logger.info(f"Validating picking {out_picking.name} as shipment received in store.")
            request.env['stock.picking'].with_user(SUPERUSER_ID).browse(out_picking.id).button_validate()
            update_status(out_picking, "RITS")
            return BaseApiResponse.success(message=f"Shipment {shipment_id} has been validated in Odoo", data={})

        elif new_status == "DTR":
            update_status(out_picking, "DTR")
            out_picking.sudo().write({'line_shipment_sate': new_status})
            # out_picking.group_id.sale_id.close_mataa_order('fully_delivered')
            return BaseApiResponse.success(message=f"Shipment {shipment_id} marked as Fully Delivered", data={})

        elif new_status == "RTRN":
            update_status(out_picking, "RTRN")
            out_picking.group_id.sale_id.close_mataa_order('fully_returned')
            return BaseApiResponse.success(message=f"Shipment {shipment_id} marked as Fully Returned", data={})

        elif new_status == "RTS":
            update_status(out_picking, "RTS")
            return BaseApiResponse.success(message=f"Shipment {shipment_id} marked as Returned To Sender", data={})

        elif new_status == "RCV":
            update_status(out_picking, "RCV")
            return BaseApiResponse.success(message=f"Shipment {shipment_id} marked as Returned to Warehouse", data={})

        elif new_status == "PKR":
            update_status(out_picking, "PKR")
            return BaseApiResponse.success(message=f"Shipment {shipment_id} marked as 'طلب شحن'", data={})

        elif new_status == "PKM":
            update_status(out_picking, "PKM")
            return BaseApiResponse.success(message=f"Shipment {shipment_id} marked as 'قيد الإلتقاط'", data={})

        elif new_status == "PKD":
            update_status(out_picking, "PKD")
            return BaseApiResponse.success(message=f"Shipment {shipment_id} marked as 'تم الإلتقاط'", data={})

        elif new_status == "RJCT":
            update_status(out_picking, "RJCT")
            return BaseApiResponse.success(message=f"Shipment {shipment_id} marked as 'مرفوضة'", data={})

        elif new_status == "OTD":
            update_status(out_picking, "OTD")
            sale_order = out_picking.sale_id or out_picking.group_id.sale_id
            if sale_order:
                sale_order.sudo().write({'mata_order_state': 'processing'})
                sale_order.update_mataa_status("processing")
            return BaseApiResponse.success(message=f"Shipment {shipment_id} marked as 'قيد التوصيل'", data={})

        elif new_status == "DEX":
            update_status(out_picking, "DEX")
            return BaseApiResponse.success(message=f"Shipment {shipment_id} marked as 'إعادة محاولة التسليم'", data={})

        elif new_status == "HTR":
            update_status(out_picking, "HTR")
            return BaseApiResponse.success(message=f"Shipment {shipment_id} marked as 'انتظار لإعادة التوصيل'", data={})

        elif new_status == "OTR":
            update_status(out_picking, "OTR")
            return BaseApiResponse.success(message=f"Shipment {shipment_id} marked as 'قيد الإرجاع'", data={})

        elif new_status == "BMR":
            update_status(out_picking, "BMR")
            return BaseApiResponse.success(message=f"Shipment {shipment_id} marked as 'وصلت إلى الفرع'", data={})

        elif new_status == "BMT":
            update_status(out_picking, "BMT")
            return BaseApiResponse.success(message=f"Shipment {shipment_id} marked as 'في الطريق إلى الفرع'", data={})

        elif new_status == "PKH":
            update_status(out_picking, "PKH")
            return BaseApiResponse.success(message=f"Shipment {shipment_id} marked as 'انتظار لإعادة الإلتقاط'",
                                           data={})

        elif new_status == "PRP":
            update_status(out_picking, "PRP")
            return BaseApiResponse.success(message=f"Shipment {shipment_id} marked as 'جاري التجهيز'", data={})

        elif new_status == "STD":
            update_status(out_picking, "STD")
            return BaseApiResponse.success(message=f"Shipment {shipment_id} marked as 'قيد الإرسال للمنذوب'", data={})

        elif new_status == "PRPD":
            update_status(out_picking, "PRPD")
            return BaseApiResponse.success(message=f"Shipment {shipment_id} marked as 'تم التجهيز'", data={})
