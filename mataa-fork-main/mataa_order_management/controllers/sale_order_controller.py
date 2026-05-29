# -*- coding: utf-8 -*-
from odoo.exceptions import ValidationError

import logging
from ..constants.sale_order_state_mapping import MATAA_STATE_MAPPING
from odoo import http
from odoo.exceptions import UserError
from odoo.http import request
import json
from odoo.addons.mataa_base.controllers.common.BaseApiResponse import BaseApiResponse
from odoo.addons.mataa_base.controllers.utility.auth_required import auth_required
import datetime
import pprint
from ..utilities.coupons_loyalty_utility import CouponsLoyaltyUtility
from ..constants.sale_order_state_mapping import MATAA_STATE_REVERSE_MAPPING

_logger = logging.getLogger(__name__)


class SaleOrderController(http.Controller):

    # ------------- SO APIs -------------
    @http.route('/api/customers/<int:customer_id>/sale_orders', type='http', auth='public', methods=['POST'],
                csrf=False)
    def create_sale_order(self, customer_id):
        api_key = request.httprequest.headers.get('X-API-KEY')
        expected_api_key = request.env['ir.config_parameter'].sudo().get_param('mataa_order_management.api_key')
        if api_key != expected_api_key:
            return BaseApiResponse.error(message="Invalid or missing API key.", status=401)
        data = json.loads(request.httprequest.data)
        _logger.info('Mataa syncing order :\n%s', pprint.pformat(data))
        # TODO: Needs review -> Removing the try-except in order to reactivation to the rollback when an error rest
        # try:
        input_customer_id = customer_id
        customer_id = request.env['res.partner'].sudo().search([
            ('id', '=', input_customer_id),
            ('customer_rank', '>', 0)
        ], limit=1)

        if not customer_id:
            return BaseApiResponse.error(
                message=f"No customer matched the provided Customer Id '{input_customer_id}'")

        if not data.get('order_lines'):
            return BaseApiResponse.error(message=f"order lines are required")

        if not data.get('city_code'):
            return BaseApiResponse.error(message=f"city_code is required")

        # TODO : investigate if the cities also need delivary method
        city_id = request.env['mataa.city'].sudo().search([('code', '=', data['city_code'])], limit=1)
        if not city_id:
            return BaseApiResponse.error(message=f"No city matched the provided code '{data['city_code']}'")

        if not data.get('mata_order_id'):
            return BaseApiResponse.error(message=f"mata_order_id is required")

        if not data.get('delivery_method'):
            return BaseApiResponse.error(message=f"delivery_method is required")

        if data.get('shipping_cost') is None:
            return BaseApiResponse.error(message=f"shipping_cost is required")
        shipping_cost = data.get('shipping_cost')
        if not isinstance(shipping_cost, (int, float)):
            return BaseApiResponse.error(message=f"shipping_cost must be a number.")
        if shipping_cost < 0:
            return BaseApiResponse.error(message=f"shipping_cost cannot be negative.")

        valid_states = [
            'wc-verifying',
            'wc-on-hold',
            'startpacking',
            'kindacompleted',
            'packingdone',
            'processing',
            'shipping',
            'completed',
            'failed',
            'cancelled',
        ]
        external_state = data.get('mata_order_state')
        if external_state is not None:
            if not isinstance(external_state, int):
                return BaseApiResponse.error(
                    message=f"Invalid mata_order_state type. Expected integer, got {type(external_state)}"
                )

            mata_order_state = MATAA_STATE_MAPPING.get(external_state)
            if mata_order_state not in valid_states:
                return BaseApiResponse.error(
                    message=f"Invalid mata_order_state: '{external_state}'. Valid range: 0-10"
                )
        else:
            mata_order_state = None

        domain = [('delivery_type', '=', data.get('delivery_method'))]
        carrier_id = request.env['delivery.carrier'].sudo().search(domain, limit=1)

        if not carrier_id:
            return BaseApiResponse.error(
                message=f"No delivery method with this type '{data.get('delivery_method')}' is found")

        if carrier_id.delivery_type == "line":
            if not city_id.line_zone_id:
                return BaseApiResponse.error(
                    message=f"Miss configuration: The selected city is not assigned to zone id")
            if not city_id.line_subzone_id:
                return BaseApiResponse.error(
                    message=f"Miss configuration: The selected city is not assigned to sub zone id")

        order_lines = []
        for line in data.get('order_lines'):
            product_id = request.env['product.product'].sudo().search([('id', '=', line['product_id'])], limit=1)
            if not product_id:
                raise UserError(f"product with id : {line['product_id']} wasn't found")

            vendor = self.get_product_supplier(product_id=product_id.id, quantity=line['qty'])

            order_lines.append((0, 0, {
                'mataa_id': line['mataa_id'],
                'product_id': product_id.id,
                'product_uom_qty': line['qty'],
                'price_unit': line['unit_price'],
                'mataa_original_price': line.get('original_price', 0.0),
                'vendor_id': vendor,
            }))

        out_of_stock_lines = []

        for line in data.get('order_lines'):
            product = request.env['product.product'].sudo().browse(line['product_id'])

            free_qty = product.get_mataa_quantity()

            if free_qty <= 0:
                out_of_stock_lines.append({
                    'product_id': product.id,
                    'isOnstock': False,
                })

        validate_stock = request.env['ir.config_parameter'].sudo().get_param('mataa_order_management.validate_api_stock',default='False')
        if validate_stock == 'True' and out_of_stock_lines:
            return request.make_response(
                json.dumps({
                    "success": False,
                    "message": "Some products are out of stock.",
                    "out_of_stock_lines": out_of_stock_lines,
                }),
                headers=[("Content-Type", "application/json")],
                status=400
            )

        mataa_payments = []
        if data.get('payments'):
            for payment in data.get('payments'):
                if not request.env['account.journal'].sudo().search([('code', '=', payment['code'])], limit=1):
                    return BaseApiResponse.error(
                        message=f"No journal matched the provided code '{payment['code']}'")
                if payment['amount'] > 0:
                    mataa_payments.append((0, 0, {
                        'code': payment['code'],
                        'payment_transaction_odoo_id': payment.get('transactionOdooId'),
                        'payment_transaction_id': payment.get('payment_transaction_id'),
                        'payment_state': payment.get('payment_state'),
                        'amount': payment['amount']
                    }))

        mataa_coupons = []
        if data.get('coupons'):
            coupons = data['coupons']
            if type(data['coupons']) is list:
                for coupon in coupons:
                    mataa_coupons.append((0, 0, {
                        'name': coupon['name'],
                        'code': coupon['code'],
                        'amount_deducted': coupon['amount_deducted']
                    }))
            else:
                mataa_coupons.append((0, 0, {
                    'name': coupons['name'],
                    'code': coupons['code'],
                    'amount_deducted': coupons['amount_deducted']}))

        actual_shipping_cost = 0.0
        is_shipping_offer = False

        shipping_offer_name = False

        offer_data = data.get('available_offer')
        if offer_data and isinstance(offer_data, dict):
            if offer_data.get('has_offer') is True:
                is_shipping_offer = True
                shipping_offer_name = offer_data.get('offer_name')
                old_cost = offer_data.get('old_shipping_cost')
                if old_cost and isinstance(old_cost, (int, float)):
                    actual_shipping_cost = old_cost

        so_mataa_create_date = data.get('mataa_order_create_date') if data.get('mataa_order_create_date') else datetime.datetime.now()
        so_vals = {'partner_id': customer_id.id,
                   'mataa_order_create_date': so_mataa_create_date,
                   'mataa_city_id': city_id.id,
                   'mata_order_id': data.get('mata_order_id'),
                   'mata_order_state': mata_order_state,
                   'order_line': order_lines,
                   'mataa_payment_ids': mataa_payments,
                   'mataa_coupon_ids': mataa_coupons,
                   'mataa_customer_note': data.get('customer_note'),
                   'internal_note': data.get('internal_note'),
                   'actual_shipping_cost': actual_shipping_cost,
                   'is_shipping_offer': is_shipping_offer,
                   'shipping_offer_name': shipping_offer_name,
                   }


        if data.get('billing'):
            so_vals.update(
                {"mata_billing_first_name": data['billing']['first_name'],
                 "mata_billing_last_name": data['billing']['last_name'],
                 "mata_billing_address_1": data['billing']['address_1'],
                 "mata_billing_address_2": data['billing']['address_2'],
                 "mata_billing_company": data['billing']['company'],
                 "mata_billing_city": data['billing']['city'],
                 "mata_billing_state": data['billing']['state'],
                 "mata_billing_country": data['billing']['country'],
                 "mata_billing_phone": data['billing']['phone'],
                 "mata_billing_postcode": data['billing']['postcode'],
                 "mata_billing_email": data['billing']['email'],
                 "mata_billing_link": data['billing']['billing_link']
                 })
        else:
            return BaseApiResponse.error(message=f"billing address is required")

        if data.get('shipping'):
            so_vals.update(
                {"mata_shipping_first_name": data['shipping']['first_name'],
                 "mata_shipping_last_name": data['shipping']['last_name'],
                 "mata_shipping_address_1": data['shipping']['address_1'],
                 "mata_shipping_address_2": data['shipping']['address_2'],
                 "mata_shipping_company": data['shipping']['company'],
                 "mata_shipping_city": data['shipping']['city'],
                 "mata_shipping_state": data['shipping']['state'],
                 "mata_shipping_country": data['shipping']['country'],
                 "mata_shipping_phone": data['shipping']['phone'],
                 "mata_shipping_postcode": data['shipping']['postcode'],
                 "mata_shipping_email": data['shipping']['email'],
                 "mata_shipping_link": data['shipping']['shipping_link']
                 })
        else:
            return BaseApiResponse.error(message=f"shipping address is required")

        order_id = request.env['sale.order'].with_context(decrease_vendor_qty=False,skip_external_sync=True,mata_order_id=data.get('mata_order_id')).sudo().create(so_vals)

        if data.get('coupon_code', False):
            coupon_code = data['coupon_code']
            order_id.add_coupon(coupon_code)
        order_id.add_delivery_method(carrier_id.id, data.get('shipping_cost'))

        if is_shipping_offer:
            delivery_line = order_id.order_line.filtered(lambda l: l.is_delivery)
            if delivery_line:
                delivery_line.sudo().write({
                    'mataa_original_price': actual_shipping_cost,
                    'price_unit': data.get('shipping_cost')
                })
        
        if carrier_id.delivery_type == 'camex':
            camex_tag = request.env.ref('mataa_order_management.so_tag_camex_order')
            order_id.mataa_tag_ids = [(4, camex_tag.id)]

        order_data = self.get_order_data(order_id.id)

        out_of_stock_lines = []

        for line in order_id.order_line:
            if line.product_id and line.product_id.detailed_type == 'product':
                qty_after = line.product_id.get_mataa_quantity()

                if qty_after == 0:
                    out_of_stock_lines.append({
                        'product_id': line.product_id.id,
                        'isOnstock': False,
                    })

        order_data.update({'out_of_stock_lines': out_of_stock_lines})

        order_id.order_line.update_line_status()
        return BaseApiResponse.created(data=order_data,message='Sales quotation created successfully')
        # except Exception as e:
        #     return BaseApiResponse.error(message=str(e))

    @http.route('/api/customers/<int:customer_id>/sale_orders', type='http', auth='public', methods=['GET'], csrf=False)
    def get_customer_sale_orders(self, customer_id, page=1, page_size=10, orderby=None, state=None):
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
        domain = [('partner_id', '=', customer_id)]
        if state:
            domain += [('state', '=', state)]
        order_ids = request.env['sale.order'].sudo().search(domain, order=ordered_by, limit=limit, offset=offset)

        sale_orders = []
        for order_id in order_ids:
            sale_orders.append(self.get_order_data(order_id.id))

        total_count = len(order_ids)
        meta = {
            'total_count': total_count,
            'page': page,
            'page_size': page_size,
            'total_pages': (total_count + page_size - 1) // page_size
        }
        return BaseApiResponse.success(data=sale_orders, meta=meta)

    @http.route('/api/customers/<int:customer_id>/sale_orders/<int:sale_order_id>', type='http', auth='public',
                methods=['GET'], csrf=False)
    def get_customer_sale_order(self, customer_id, sale_order_id):
        api_key = request.httprequest.headers.get('X-API-KEY')
        expected_api_key = request.env['ir.config_parameter'].sudo().get_param('mataa_order_management.api_key')
        if api_key != expected_api_key:
            return BaseApiResponse.error(message="Invalid or missing API key.", status=401)

        order_id = request.env['sale.order'].sudo().search(
            [('id', '=', sale_order_id), ('partner_id', '=', customer_id)])

        return BaseApiResponse.success(data=self.get_order_data(order_id.id))

    @http.route('/api/customers/<int:customer_id>/sale_orders/<int:sale_order_id>/details', type='http', auth='public',
                methods=['GET'], csrf=False)
    def get_customer_sale_order_lines(self, customer_id, sale_order_id):
        api_key = request.httprequest.headers.get('X-API-KEY')
        expected_api_key = request.env['ir.config_parameter'].sudo().get_param('mataa_order_management.api_key')
        if api_key != expected_api_key:
            return BaseApiResponse.error(message="Invalid or missing API key.", status=401)

        order_id = request.env['sale.order'].sudo().search(
            [('id', '=', sale_order_id), ('partner_id', '=', customer_id)])

        lines_data = []
        for line in order_id.order_line:
            lines_data.append(self.get_order_line_data(line.id))
        return BaseApiResponse.success(data=lines_data)

    # ------------- Delivery APIs -------------
    @http.route('/api/delivery_cost/<string:delivery_method>/<int:city_id>', type='http', auth='public',
                methods=['GET'], csrf=False)
    def get_delivery_cost(self, delivery_method, city_id):
        api_key = request.httprequest.headers.get('X-API-KEY')
        expected_api_key = request.env['ir.config_parameter'].sudo().get_param('mataa_order_management.api_key')
        if api_key != expected_api_key:
            return BaseApiResponse.error(message="Invalid or missing API key.", status=401)
        domain = [('id', '=', city_id)]
        city_id = request.env['mataa.city'].sudo().search(domain, limit=1)

        cost = 0
        if hasattr(city_id, '%s_get_delivery_cost' % delivery_method):
            cost = getattr(city_id, '%s_get_delivery_cost' % delivery_method)()

        return BaseApiResponse.success(data={'cost': cost})

    # ------------- Wallet APIs -------------
    @http.route('/api/customers/<int:customer_id>/wallet_transactions', type='http', auth='public', methods=['GET'],
                csrf=False)
    def get_customer_wallet_transactions(self, customer_id, page=1, page_size=10, orderby=None):
        api_key = request.httprequest.headers.get('X-API-KEY')
        expected_api_key = request.env['ir.config_parameter'].sudo().get_param('mataa_order_management.api_key')
        if api_key != expected_api_key:
            return BaseApiResponse.error(message="Invalid or missing API key.", status=401)
        page = int(page)
        page_size = int(page_size)
        offset = (page - 1) * page_size
        limit = page_size

        partner_id = request.env['res.partner'].with_context(active_test=False).sudo().search(
            [('id', '=', customer_id)])

        # TODO: Update the way of how the company record has been fetched
        company_id = request.env['res.company'].sudo().search([('id', '=', 1)], limit=1)
        reservation_journal_id = company_id.wallet_reservation_journal_id

        ordered_by = 'date DESC'
        if orderby == 'asc':
            ordered_by = 'date ASC'

        domain = [('partner_id', '=', customer_id),
                  ('parent_state', '=', 'posted'),
                  ('account_id', '=', partner_id.with_company(company_id).property_account_receivable_id.id),
                  '|',
                  ('journal_id', '!=', reservation_journal_id.id),
                  '&',
                  ('journal_id', '=', reservation_journal_id.id),
                  '&',
                  ('move_id.reversal_move_id', '=', False),
                  ('move_id.reversed_entry_id', '=', False),
                  ]

        aml_ids = request.env['account.move.line'].sudo().search(domain, order=ordered_by, limit=limit, offset=offset)

        aml_data = []
        for aml_id in aml_ids:
            aml_data.append(self.get_aml_data(aml_id.id))

        total_count = len(aml_ids)

        meta = {
            'total_count': total_count,
            'page': page,
            'page_size': page_size,
            'total_pages': (total_count + page_size - 1) // page_size
        }
        return BaseApiResponse.success(data=aml_data, meta=meta)

    # ------------- Payment APIs -------------
    @http.route('/api/report_payment_error', type='http', auth='public', methods=['POST'], csrf=False)
    def report_payment_error(self, **kwargs):
        api_key = request.httprequest.headers.get('X-API-KEY')
        expected_api_key = request.env['ir.config_parameter'].sudo().get_param('mataa_order_management.api_key')
        if api_key != expected_api_key:
            return BaseApiResponse.error(message="Invalid or missing API key.", status=401)
        data = json.loads(request.httprequest.data)
        custoreodooid = data.get('custoreodooid')
        error = data.get('error')
        payment_type = data.get('payment_type')

        if not custoreodooid or not error or not payment_type:
            return request.make_response(
                json.dumps({'success': False, 'message': 'Missing required fields.'}),
                headers=[('Content-Type', 'application/json')]
            )

        team = request.env['helpdesk.team'].sudo().search([('name', '=', 'Customer Care')], limit=1)
        if not team:
            return request.make_response(
                json.dumps({'success': False, 'message': 'Customer Care team not found.'}),
                headers=[('Content-Type', 'application/json')]
            )

        tag = request.env['helpdesk.tag'].sudo().search([('name', '=', 'فشل الدفع')], limit=1)
        if not tag:
            tag = request.env['helpdesk.tag'].sudo().create({'name': 'فشل الدفع'})

        ticket = request.env['helpdesk.ticket'].sudo().create({
            'partner_id': custoreodooid,
            'team_id': team.id,
            'name': f'فشل عملية الدفع بواسطة: {payment_type}',
            'description': error,
            'tag_ids': [(6, 0, [tag.id])],
        })

        return request.make_response(
            json.dumps({'success': True, 'ticket_id': ticket.id}),
            headers=[('Content-Type', 'application/json')]
        )

    @http.route('/api/report_bank_transfer', type='http', auth='public', methods=['POST'], csrf=False)
    def report_bank_transfer(self, **kwargs):
        api_key = request.httprequest.headers.get('X-API-KEY')
        expected_api_key = request.env['ir.config_parameter'].sudo().get_param('mataa_order_management.api_key')
        
        if api_key != expected_api_key:
            return request.make_response(json.dumps({'success': False, 'message': 'Invalid API key.'}), headers=[('Content-Type', 'application/json')], status=401)
        
        config = request.env['ir.config_parameter'].sudo()
        team = int(config.get_param('mataa_order_management.report_bank_transfer_team_name'))
        stage_name = config.get_param('mataa_order_management.report_bank_transfer_stage_name')
        tag_name = config.get_param('mataa_order_management.report_bank_transfer_tag_name')
        ticket_name = config.get_param('mataa_order_management.report_bank_transfer_ticket_name')
        
        data = json.loads(request.httprequest.data)
        odooid = data.get('customer_id')
        description = data.get('description')

        if not team:
            return request.make_response(json.dumps({'success': False, 'message': 'Finance team not found.'}), headers=[('Content-Type', 'application/json')])

        stage = request.env['helpdesk.stage'].sudo().search([
            ('name', '=', stage_name),
            ('team_ids', 'in', team)
        ], limit=1)

        if not stage:
            stage = request.env['helpdesk.stage'].sudo().create({
                'name': stage_name,
                'team_ids': [(4, team)],
                'sequence': 10,
            })

        stage_id = stage.id if stage else False

        tag = request.env['helpdesk.tag'].sudo().search([('name', '=', tag_name)], limit=1)
        if not tag:
            tag = request.env['helpdesk.tag'].sudo().create({'name': tag_name})

        ticket_vals = {
            'partner_id': int(odooid),
            'team_id': team,
            'name': ticket_name,
            'description': description,
            'tag_ids': [(6, 0, [tag.id])],
        }
        
        if stage_id:
            ticket_vals['stage_id'] = stage_id

        ticket = request.env['helpdesk.ticket'].sudo().create(ticket_vals)

        return request.make_response(
            json.dumps({'success': True, 'ticket_id': ticket.id}),
            headers=[('Content-Type', 'application/json')]
        )
    

    @http.route('/api/ims/order_issue', type='http', auth='public', methods=['POST'], csrf=False)
    def report_order_issue(self, **kwargs):
        api_key = request.httprequest.headers.get('X-API-KEY')
        expected_api_key = request.env['ir.config_parameter'].sudo().get_param('mataa_order_management.api_key')

        if api_key != expected_api_key:
            return request.make_response(
                json.dumps({'success': False, 'message': 'Invalid API key.'}),
                headers=[('Content-Type', 'application/json')],
                status=401
            )

        config = request.env['ir.config_parameter'].sudo()
        team_id = int(config.get_param(
            'mataa_order_management.report_order_issue_team_name',
        ))
        stage_name = config.get_param(
            'mataa_order_management.report_order_issue_stage_name',
        )

        data = json.loads(request.httprequest.data)
        product_sku = data.get('product_sku')
        issue_type = data.get('issue_type')
        reason = data.get('reason')
        order_id = data.get('order_id')

        if not issue_type or not order_id:
            return BaseApiResponse.error(message="issue_type and order_id are required.", status=400)

        if not team_id:
            return BaseApiResponse.error(message="Order issue team not found.", status=400)

        team = request.env['helpdesk.team'].sudo().browse(team_id)
        if not team:
            return BaseApiResponse.error(message="Order issue team not found.", status=400)

        if product_sku:
            product = request.env['product.product'].sudo().search([('default_code', '=', product_sku)], limit=1)
            if not product:
                return BaseApiResponse.error(message="Product with given SKU not found", status=404)

        sale_order = request.env['sale.order'].sudo().browse(int(order_id))
        if not sale_order.exists():
            return BaseApiResponse.error(message="Sale order not found", status=404)

        stage = request.env['helpdesk.stage'].sudo().search([
            ('name', '=', stage_name),
            ('team_ids', 'in', [team_id])
        ], limit=1)

        if not stage and stage_name:
            stage = request.env['helpdesk.stage'].sudo().create({
                'name': stage_name,
                'team_ids': [(4, team.id)],
                'sequence': 10,
            })

        tag_name = issue_type
        tag = request.env['helpdesk.tag'].sudo().search([('name', '=', tag_name)], limit=1)
        if not tag:
            tag = request.env['helpdesk.tag'].sudo().create({'name': tag_name})

        description = f"Purpose: {issue_type}"
        if reason:
            description = f"{description}<br/>Description: {reason}"
        if product_sku:
            description = f"Product SKU: {product_sku}<br/>{description}"

        ticket_vals = {
            'team_id': team.id,
            'name': f"Order: {sale_order.name}",
            'description': description,
            'mataa_so_id': sale_order.id,
        }

        if product:
            ticket_vals['mataa_product_id'] = product.id

        if sale_order.partner_id:
            ticket_vals['partner_id'] = sale_order.partner_id.id
            ticket_vals['mataa_customer_id'] = sale_order.partner_id.id
            ticket_vals['partner_phone'] = sale_order.partner_id.phone

        if tag:
            ticket_vals['tag_ids'] = [(6, 0, [tag.id])]

        if stage:
            ticket_vals['stage_id'] = stage.id

        ticket = request.env['helpdesk.ticket'].sudo().create(ticket_vals)

        return BaseApiResponse.success(data={'ticket_id': ticket.id})
    # ------------- Utilities -------------

    def get_customer_by_mataa_id(self, mataa_customer_id):
        customer = request.env['res.partner'].sudo().search([
            ('mataa_id', '=', mataa_customer_id),
            ('supplier_rank', '=', 0)
        ], limit=1)

        return customer

    def get_product_supplier(self, product_id, quantity):
        product = request.env['product.product'].sudo().browse(product_id)

        if product.free_qty >= quantity:
            vendor = None
            return vendor

        vendor_info = request.env['product.supplierinfo'].sudo().search([
            ('product_id', '=', product.id),
            ('min_qty', '>=', quantity),
            ('published', '=', True),
        ], order='sequence', limit=1)

        vendor = vendor_info and vendor_info.partner_id.id or None

        return vendor

    def get_order_data(self, order_id):
        order_id = request.env['sale.order'].sudo().browse(order_id)
        external_status = MATAA_STATE_REVERSE_MAPPING.get(order_id.mata_order_state)
        order_data = {
            'id': order_id.id,
            'mata_order_id': order_id.mata_order_id,
            'create_date': str(order_id.create_date),
            'write_date': str(order_id.write_date),
            'date_order': str(order_id.date_order) if order_id.date_order else None,
            'mataa_order_create_date': str(order_id.mataa_order_create_date) if order_id.mataa_order_create_date else None,
            'state': order_id.state,
            'mata_order_state': external_status,
            'name': order_id.name,
            'total': order_id.amount_total,
        }
        return order_data

    def get_order_line_data(self, order_line_id):
        line = request.env['sale.order.line'].sudo().browse(order_line_id)

        line_data = {
            'line_id': line.id,
            'mataa_id': line.mataa_id,
            'product_id': line.product_id.id,
            'product_mataa_id': line.product_id.mataa_id,

            'create_date': str(line.create_date),
            'write_date': str(line.write_date),

            'product_name': line.product_id.name,
            'product_sku': line.product_id.default_code if line.product_id.default_code else None,

            'description': line.name,
            'quantity': line.product_uom_qty,
            'unit_price': line.price_unit,
        }
        return line_data

    def get_aml_data(self, aml_id):
        aml_id = request.env['account.move.line'].sudo().browse(aml_id)
        aml_data = {
            'id': aml_id.id,
            'date': str(aml_id.date),
            'ref': aml_id.ref,
            'name': aml_id.name,
            'amount': aml_id.balance * -1,
        }
        return aml_data

    @http.route('/api/v1/order/calculate_totals', type='http', auth='public', methods=['POST'],
                csrf=False)
    def calculate_totals(self):
        data = json.loads(request.httprequest.data)
        coupon_code = data.get('coupon_code')
        mataa_customer_id = data.get('partner_id')
        # try:
        customer_id = request.env['res.partner'].sudo().search([
            ('mataa_id', '=', mataa_customer_id),
            ('customer_rank', '>', 0)
        ], limit=1)
        if not customer_id:
            return BaseApiResponse.error(
                message=f"No customer matched the provided Customer Id '{mataa_customer_id}'")

        if not data.get('order_lines'):
            return BaseApiResponse.error(message=f"order lines are required")

        order_lines = data.get('order_lines')
        self.auto_apply_coupon(customer_id, coupon_code, order_lines)
        return BaseApiResponse.success(data=order_lines)

    def auto_apply_coupon(self, customer_id, coupon_code, order_lines):
        coupons_points = dict()
        status = CouponsLoyaltyUtility._try_apply_code(request.env, customer_id, coupon_code, order_lines, coupons_points)
        if 'error' in status:
            raise ValidationError(status['error'])
        all_rewards = request.env['loyalty.reward']
        for rewards in status.values():
            all_rewards |= rewards
        if not all_rewards:
            raise ValidationError(_('No reward found.'))
        claimable_rewards = CouponsLoyaltyUtility._get_claimable_rewards(request.env, coupons_points, order_lines,
                                                                         coupon_code=coupon_code)
        selected_coupon = False
        for coupon, rewards in claimable_rewards.items():
            if all_rewards[0] in rewards:
                selected_coupon = coupon
                break
        if not selected_coupon:
            raise ValidationError(_('Coupon not found while trying to add the following reward: %s', all_rewards[0].description))

        if not all_rewards[0].reward_type == 'product':
            selected_product_id = False
        else:
            selected_product_id = all_rewards[0].reward_product_ids[:1]

        CouponsLoyaltyUtility._apply_program_reward(request.env, all_rewards[0], selected_coupon, coupons_points,
                                                    order_lines, product=selected_product_id)
