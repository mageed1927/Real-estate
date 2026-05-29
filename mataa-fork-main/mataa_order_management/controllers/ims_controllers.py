from odoo import http
from odoo.http import request
from odoo.addons.mataa_base.controllers.common.BaseApiResponse import BaseApiResponse
import json
import uuid

class IMSController(http.Controller):

    def _validate_api_key(self):
        api_key = request.httprequest.headers.get('X-API-KEY')
        expected_api_key = request.env['ir.config_parameter'].sudo().get_param('mataa_order_management.api_key')
        if api_key != expected_api_key:
            return False
        return True

    def get_ims_orders(self, sale_order_id=None):
        if not self._validate_api_key():
            return BaseApiResponse.error(message="Invalid or missing API key.", status=401)

        if sale_order_id:
            orders_ids = [sale_order_id]
        else:
            orders_ids = request.env['sale.order'].sudo().search([
                "&", "&", ("mata_order_state", "in", ["startpacking", "kindacompleted"]),
                ("is_suspended", "=", False), ("state", "!=", "cancel"),
                ]).mapped('id')

        pickings = request.env['stock.picking'].sudo().search([
            ("mataa_sale_order_id", "in", orders_ids),
            ('picking_type_id', 'in', [3, 4]),
            ('location_dest_id', 'in', ["WH/Output","WH/Packing Zone"]),
            ('state', 'in', ['assigned', 'done', 'waiting'])     
        ])
        
        pickings_data_by_origin = {}
        for picking in pickings:

            data ={
                    'id': picking.id,
                    'name': picking.name,
                    'picking_type': 'Pack' if picking.picking_type_id.id == 4 else 'Pick',
                    'priority': picking.priority,
                    'creation_date': picking.create_date.isoformat() if picking.create_date else None,
                    'sale_order_id': picking.mataa_sale_order_id.id,
                    'sale_order_name': picking.origin,
                    'mataa_bundle_id': picking.mataa_bundle_id.id if picking.mataa_bundle_id else None,
                    'state': picking.state,
                    'destination': picking.location_dest_id.complete_name,
                    'note': self._get_clean_note(picking),
                    'so_tags': picking.mataa_sale_order_id.mataa_tag_ids.mapped('name'),
                    'moves_data': self._get_moves_data(picking.id),
                    'delivery_type': picking.delivery_type
                    }
            origin = picking.origin
            
            if origin not in pickings_data_by_origin:
                pickings_data_by_origin[origin] = []
            pickings_data_by_origin[origin].append(data)


        result = []
        for origin, data in pickings_data_by_origin.items():
            if not sale_order_id:
                states = [p['state'] for p in data]
                if 'assigned' not in states or len(states) > 2:
                    continue
            result.append({
                "origin": origin,
                "data": data
            })

        return BaseApiResponse.success(data=result)

    def _get_clean_note(self, picking):
        so = picking.mataa_sale_order_id
        if not so:
            return ""
        
        notes = []
        if so.internal_note:
            notes.append(f"Internal Note: {so.internal_note}")
        if so.mataa_customer_note:
            notes.append(so.mataa_customer_note)
            
        return "\n".join(notes)


    def _get_moves_data(self, picking_id):
        picking = request.env['stock.move'].sudo().search([('picking_id', '=', picking_id)])    
           
        
        moves_data = []
        for move in picking:
            line = request.env['stock.move.line'].sudo().search([('move_id', '=', move.id)]) 

            packages = list(set(line.mapped('package_id.name')))
            if not packages:
                packages = [line.package_id.name]

            barcodes = []
            if move.product_id.barcode:
                barcodes.append(move.product_id.barcode)
            if move.product_id.barcode_ids:
                barcodes.extend(move.product_id.barcode_ids.mapped('name'))

            moves_data.append({
                'id': move.id,
                'product_id': move.product_id.id if move.product_id else None,
                'product_name': move.product_id.name,
                "sku": move.product_id.default_code,
                'product_image_url': move.product_id.product_tmpl_id.main_image if move.product_id else None,
                'demand': move.product_uom_qty,
                'available_quantity': move.product_qty,
                'quantity_picked': move.quantity,
                'source_location': move.location_id.complete_name,
                'destination_location': move.location_dest_id.complete_name,
                'packages': packages,
                'barcodes': barcodes,
                'is_picked': move.picked
            })
        return moves_data

    @http.route('/api/ims/order/<int:order_id>', type='http', auth='public', methods=['GET'], csrf=False)
    def get_single_order(self, order_id):
        if not self._validate_api_key():
            return BaseApiResponse.error(message="Invalid or missing API key.", status=401)

        return self.get_ims_orders(sale_order_id=order_id)

    @http.route('/api/ims/orders', type='http', auth='public', methods=['GET'], csrf=False)
    def get_orders(self):
        if not self._validate_api_key():
            return BaseApiResponse.error(message="Invalid or missing API key.", status=401)

        return self.get_ims_orders()

    @http.route('/api/ims/source/<int:picking_id>', type='http', auth='public', methods=['POST'], csrf=False)
    def scan_source_location(self, picking_id):
        if not self._validate_api_key():
            return BaseApiResponse.error(message="Invalid or missing API key.", status=401)
        
        data = json.loads(request.httprequest.data)

        picking = request.env['stock.picking'].sudo().search([('id', '=', picking_id)])
        if not picking:
            return BaseApiResponse.error(message="Picking not found.")
        
        source_location = data.get('location')
        if not source_location:
            return BaseApiResponse.error(message="Source location is required.")
        
        moves_to_proccess = []
        for move in picking:
            if move.location_id.complete_name == source_location:
                moves_to_proccess.append(move.id)
        if not moves_to_proccess:
            return BaseApiResponse.error(message="No moves to process from this location.")
        
        return BaseApiResponse.success(data=moves_to_proccess, message="Moves to process from this location.")


    def _process_move_with_barcode(self, picking_id, barcode, done_qty):
        picking = request.env['stock.picking'].sudo().browse(picking_id)
        if not picking.exists():
            return None, "Picking not found."

        target_move = request.env['stock.move'].sudo().search([
            ('picking_id', '=', picking_id), ('product_id.barcode', '=', barcode)
        ])

        if not target_move:
            return None, "No matching move found in this picking."

        if target_move.picked:
            return None, "Move was already proceeded."

        if done_qty > target_move.product_uom_qty:
            return None, "Demand exceeded."
        elif done_qty == target_move.product_uom_qty:
            target_move.picked = True
            return {
                "state": "done"
            }, "Demand met."

        return {
            "state": "partial"
        }, f"remaining: {target_move.product_uom_qty - done_qty}"

    @http.route('/api/ims/pick/<int:picking_id>', type='http', auth='public', methods=['post'], csrf=False)
    def pick_move(self, picking_id):
        api_key = request.httprequest.headers.get('X-API-KEY')
        expected_api_key = request.env['ir.config_parameter'].sudo().get_param('mataa_order_management.api_key')
        if api_key != expected_api_key:
            return BaseApiResponse.error(message="Invalid or missing API key.", status=401)

        data = json.loads(request.httprequest.data)
        barcode = data.get('barcode')
        if not barcode:
             return BaseApiResponse.error(message="Barcode is required.")
        
        done_qty = data.get('done_qty')
        if not done_qty:
            return BaseApiResponse.error(message="Done quantity is required.")

        res, msg = self._process_move_with_barcode(picking_id, barcode, done_qty)
        if not res:
            return BaseApiResponse.error(message=msg)

        return BaseApiResponse.success(data=res, message=msg)


    @http.route('/api/ims/pack/<int:picking_id>', type='http', auth='public', methods=['post'], csrf=False)
    def pack_move(self, picking_id):
        if not self._validate_api_key():
            return BaseApiResponse.error(message="Invalid or missing API key.", status=401)
        
        data = json.loads(request.httprequest.data)
        barcode = data.get('barcode')
        if not barcode:
            return BaseApiResponse.error(message="Barcode is required.")
        
        done_qty = data.get('done_qty')
        if not done_qty:
            return BaseApiResponse.error(message="Done quantity is required.")
        
        res, msg = self._process_move_with_barcode(picking_id, barcode, done_qty)
        if not res:
            return BaseApiResponse.error(message=msg)

        return BaseApiResponse.success(data=res, message="Move packed successfully.")

    @http.route('/api/ims/destination/<int:picking_id>', type='http', auth='public', methods=['POST'], csrf=False)
    def scan_destination_location(self, picking_id):
        if not self._validate_api_key():
            return BaseApiResponse.error(message="Invalid or missing API key.", status=401)
        
        data = json.loads(request.httprequest.data)
        destination_location = data.get('location')
        package_name = data.get('package')

        if not destination_location:
            return BaseApiResponse.error(message="Destination location is required.")
        
        picking = request.env['stock.picking'].sudo().browse(picking_id)
        if not picking.exists():
            return BaseApiResponse.error(message="Picking not found.")
        
        if package_name:
            package = request.env['stock.quant.package'].sudo().search([('name', '=', package_name)], limit=1)
            if not package:
                package = request.env['stock.quant.package'].sudo().create({'name': package_name})
            picking.move_line_ids.write({'result_package_id': package.id})

        if any(move.state not in ('done', 'cancel') and not move.picked for move in picking.move_ids):
            return BaseApiResponse.error(message="Some moves are not done yet.")
        
        # If all moves are picked/done, we can try to validate the picking if not done
        if picking.state != 'done':
            picking.with_context(skip_pack_validate_wizard=True).button_validate()
            return BaseApiResponse.success(data={
                "picking_id": picking.id,
                "delivary_type": picking.carrier_id.name,
                "tracking_ref": picking.carrier_tracking_ref or None
            }, message="Picking moved to destination location successfully.") 
        
        return BaseApiResponse.error(message="Invalid destination location.") 
    
    @http.route('/api/ims/bundle', type='http', auth='public', methods=['POST'], csrf=False)
    def validate_bundle(self):
        if not self._validate_api_key():
            return BaseApiResponse.error(message="Invalid or missing API key.", status=401)
        
        data = json.loads(request.httprequest.data)
        bundle_id = data.get('bundle_id')
        if not bundle_id:
            return BaseApiResponse.error(message="Bundle id is required.")
        
        packs = request.env['stock.picking'].sudo().search([
            ('mataa_sale_order_id.mataa_bundle_id.id', '=', bundle_id),
            ('picking_type_id', '=', 4)
        ])
        if not packs.exists():
            return BaseApiResponse.error(message="Packing not found.")
        
        if any(pack.state != 'assigned' for pack in packs):
            return BaseApiResponse.error(message="Some packs are not assigned.")
        delivery_type = packs[0].carrier_id.name
        if any(pack.carrier_id.name != delivery_type for pack in packs):
            return BaseApiResponse.error(message="Some packs have different delivery types.")
        tracking_ref = packs[0].carrier_tracking_ref
        if any(pack.carrier_tracking_ref != tracking_ref for pack in packs):
            return BaseApiResponse.error(message="Some packs have different tracking refs.")
        
        try:
            packs[0].with_context(skip_pack_validate_wizard=True, skip_bundle_pack_confirmation=True).button_validate()
        except Exception as e:
            return BaseApiResponse.error(message=str(e))
        
        return BaseApiResponse.success(data={
            "bundle_id": bundle_id,
            "orders": packs.mapped('mataa_sale_order_id.name'),
            "delivery_type": delivery_type,
            "tracking_ref": tracking_ref or None
        }, message="bundled packs validated successfully."
        )


    @http.route('/api/ims/print/<int:so_id>', type='http', auth='public', methods=['GET'], csrf=False)
    def create_invoice(self, so_id):
        if not self._validate_api_key():
            return BaseApiResponse.error(message="Invalid or missing API key.", status=401)
        

        picking = request.env['stock.picking'].sudo().search([
            ('mataa_sale_order_id', '=', so_id),
            ('picking_type_id', '=', 2)
        ])
        if not picking.exists() or len(picking) > 1:
            return BaseApiResponse.error(message="Invalid so id or so has multiple out moves.")
        
        invoice_report = request.env['ir.actions.report'].sudo().browse(979)
        if not invoice_report.exists():
            return BaseApiResponse.error(message="Invoice report not found.")
        
        invoice_content, _ = invoice_report.sudo()._render_qweb_pdf(
            invoice_report.report_name, 
            [so_id]
        )
        delivery_slip_content = False
        if picking.carrier_id.name == 'Camex':
            delivery_slip_report = request.env['ir.actions.report'].sudo().browse(1142)
            if not delivery_slip_report.exists():
                return BaseApiResponse.error(message="Delivery slip report not found.")
            
            delivery_slip_content, _ = delivery_slip_report.sudo()._render_qweb_pdf(
                delivery_slip_report.report_name, 
                [picking.id]
            )
        
        boundary = uuid.uuid4().hex
        parts = []

        # ---- json Part
        json_data = {
            "delivary_type": picking.carrier_id.name or "",
            "tracking_ref": picking.carrier_tracking_ref or None
        }

        parts.append(
            (
                f'--{boundary}\r\n'
                'Content-Type: application/json; charset=utf-8\r\n'
                'Content-Disposition: inline\r\n'
                '\r\n'
                f'{json.dumps(json_data)}\r\n'
            ).encode('utf-8')
        )

        # ---- Invoice PDF
        parts.append(
            (
                f'--{boundary}\r\n'
                'Content-Type: application/pdf\r\n'
                f'Content-Disposition: attachment; '
                f'filename="{picking.mataa_sale_order_id.name}-invoice.pdf"\r\n'
                '\r\n'
            ).encode('utf-8') + invoice_content + b'\r\n'
        )

        # ---- Delivery Slip PDF
        if delivery_slip_content:
            parts.append(
                (
                    f'--{boundary}\r\n'
                    'Content-Type: application/pdf\r\n'
                    f'Content-Disposition: attachment; '
                    f'filename="{picking.mataa_sale_order_id.name}-delivery-slip.pdf"\r\n'
                    '\r\n'
                ).encode('utf-8') + delivery_slip_content + b'\r\n'
            )

        # ---- Closing boundary
        parts.append(f'--{boundary}--\r\n'.encode('utf-8'))

        body = b''.join(parts)

        headers = {
            'Content-Type': f'multipart/mixed; boundary={boundary}',
            'Content-Length': str(len(body)),
        }


        return request.make_response(body, headers)
