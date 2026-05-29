# -*- coding: utf-8 -*-

from odoo import http
from odoo.http import request
import json
import logging
from datetime import datetime, timedelta
from odoo.addons.mataa_base.controllers.common.BaseApiResponse import BaseApiResponse
from odoo import fields

_logger = logging.getLogger(__name__)


class VMSController(http.Controller):
    """Vendor Management System (VMS) API Controller"""

    # ============================================================================
    # MAIN VMS ENDPOINTS
    # ============================================================================

    @http.route('/api/vendors/<int:vendor_id>/vms/main', type='http', auth='public', methods=['GET'], csrf=False)
    def vms_main(self, vendor_id):
        api_key = request.httprequest.headers.get('X-API-KEY')
        expected_api_key = request.env['ir.config_parameter'].sudo().get_param('mataa_order_management.api_key')
        if api_key != expected_api_key:
            return BaseApiResponse.error(message="Invalid or missing API key.", status=401)
        """Main VMS endpoint - returns vendor balances and summary"""
        try:
            vendor = request.env['res.partner'].sudo().browse(vendor_id)
            if not vendor.exists() or not vendor.is_vms_vendor:
                return BaseApiResponse.not_found('VMS Vendor not found')

            vendor_data = vendor.get_vms_vendor_data()

            # Get balances
            balances = {
                'all_transactions': vendor_data['balances']['total'],
                'outstanding': vendor_data['balances']['outstanding'],
                'shipping': vendor_data['balances']['shipping'],
                'cancelled': vendor_data['balances']['cancelled'],
            }

            # Get summary counts
            summary = self._get_vendor_summary(vendor_id)

            response_data = {
                'vendor': vendor_data,
                'balances': balances,
                'summary': summary,
                'timestamp': datetime.now().isoformat()
            }

            return BaseApiResponse.success(data=response_data)

        except Exception as e:
            _logger.error(f'Error in VMS main endpoint: {str(e)}')
            return BaseApiResponse.error(message=str(e))

    @http.route('/api/vendors/<int:vendor_id>/vms/po_view/<int:po_id>', type='http', auth='public', methods=['GET'], csrf=False)
    def vms_po_view(self, vendor_id, po_id):
        api_key = request.httprequest.headers.get('X-API-KEY')
        expected_api_key = request.env['ir.config_parameter'].sudo().get_param('mataa_order_management.api_key')
        if api_key != expected_api_key:
            return BaseApiResponse.error(message="Invalid or missing API key.", status=401)
        """Get specific Purchase Order details"""
        try:
            vendor = request.env['res.partner'].sudo().browse(vendor_id)
            if not vendor.exists() or not vendor.is_vms_vendor:
                return BaseApiResponse.not_found('VMS Vendor not found')
            
            vendor_data = vendor.get_vms_vendor_data()

            # Get PO data
            po = request.env['purchase.order'].sudo().search([
                ('id', '=', po_id),
                ('partner_id', 'in', self._get_related_vendor_ids(vendor_data))
            ], limit=1)

            if not po:
                return BaseApiResponse.not_found('Purchase Order not found for this vendor')

            po_data = po.get_vms_po_data()
            return BaseApiResponse.success(data=po_data)

        except Exception as e:
            _logger.error(f'Error in VMS PO view endpoint: {str(e)}')
            return BaseApiResponse.error(message=str(e))

    # ============================================================================
    # STOCK ENDPOINTS
    # ============================================================================

    @http.route('/api/vendors/<int:vendor_id>/vms/stock/standard', type='http', auth='public', methods=['GET'], csrf=False)
    def vms_stock_standard(self, vendor_id):
        api_key = request.httprequest.headers.get('X-API-KEY')
        expected_api_key = request.env['ir.config_parameter'].sudo().get_param('mataa_order_management.api_key')
        if api_key != expected_api_key:
            return BaseApiResponse.error(message="Invalid or missing API key.", status=401)
        """Get daily order totals for standard stock"""
        try:
            vendor = request.env['res.partner'].sudo().browse(vendor_id)
            if not vendor.exists() or not vendor.is_vms_vendor:
                return BaseApiResponse.not_found('VMS Vendor not found')
            
            vendor_data = vendor.get_vms_vendor_data()
            stock_data = self._get_standard_stock_data(vendor_data)
            return BaseApiResponse.success(data=stock_data)

        except Exception as e:
            _logger.error(f'Error in VMS standard stock endpoint: {str(e)}')
            return BaseApiResponse.error(message=str(e))

    @http.route('/api/vendors/<int:vendor_id>/vms/stock/return', type='http', auth='public', methods=['GET'], csrf=False)
    def vms_stock_return(self, vendor_id):
        api_key = request.httprequest.headers.get('X-API-KEY')
        expected_api_key = request.env['ir.config_parameter'].sudo().get_param('mataa_order_management.api_key')
        if api_key != expected_api_key:
            return BaseApiResponse.error(message="Invalid or missing API key.", status=401)
        """Get products in return area"""
        try:
            vendor = request.env['res.partner'].sudo().browse(vendor_id)
            if not vendor.exists() or not vendor.is_vms_vendor:
                return BaseApiResponse.not_found('VMS Vendor not found')

            vendor_data = vendor.get_vms_vendor_data()
            return_data = self._get_return_stock_data(vendor_data)
            return BaseApiResponse.success(data=return_data)

        except Exception as e:
            _logger.error(f'Error in VMS return stock endpoint: {str(e)}')
            return BaseApiResponse.error(message=str(e))

    @http.route('/api/vendors/<int:vendor_id>/vms/stock/in_house', type='http', auth='public', methods=['GET'], csrf=False)
    def vms_stock_in_house(self, vendor_id):
        api_key = request.httprequest.headers.get('X-API-KEY')
        expected_api_key = request.env['ir.config_parameter'].sudo().get_param('mataa_order_management.api_key')
        if api_key != expected_api_key:
            return BaseApiResponse.error(message="Invalid or missing API key.", status=401)
        """Get goods received at in-house location"""
        try:
            vendor = request.env['res.partner'].sudo().browse(vendor_id)
            if not vendor.exists() or not vendor.is_vms_vendor:
                return BaseApiResponse.not_found('VMS Vendor not found')

            vendor_data = vendor.get_vms_vendor_data()
            inhouse_data = self._get_inhouse_stock_data(vendor_data)
            return BaseApiResponse.success(data=inhouse_data)

        except Exception as e:
            _logger.error(f'Error in VMS in-house stock endpoint: {str(e)}')
            return BaseApiResponse.error(message=str(e))

    # ============================================================================
    # SHIPPING ENDPOINTS
    # ============================================================================

    @http.route('/api/vendors/<int:vendor_id>/vms/shipping/standard', type='http', auth='public', methods=['GET'], csrf=False)
    def vms_shipping_standard(self, vendor_id):
        api_key = request.httprequest.headers.get('X-API-KEY')
        expected_api_key = request.env['ir.config_parameter'].sudo().get_param('mataa_order_management.api_key')
        if api_key != expected_api_key:
            return BaseApiResponse.error(message="Invalid or missing API key.", status=401)
        """Get daily order shipping products"""
        try:
            vendor = request.env['res.partner'].sudo().browse(vendor_id)
            if not vendor.exists() or not vendor.is_vms_vendor:
                return BaseApiResponse.not_found('VMS Vendor not found')

            vendor_data = vendor.get_vms_vendor_data()
            shipping_data = self._get_standard_shipping_data(vendor_data)
            return BaseApiResponse.success(data=shipping_data)

        except Exception as e:
            _logger.error(f'Error in VMS standard shipping endpoint: {str(e)}')
            return BaseApiResponse.error(message=str(e))

    @http.route('/api/vendors/<int:vendor_id>/vms/shipping/in_house', type='http', auth='public', methods=['GET'], csrf=False)
    def vms_shipping_in_house(self, vendor_id):
        api_key = request.httprequest.headers.get('X-API-KEY')
        expected_api_key = request.env['ir.config_parameter'].sudo().get_param('mataa_order_management.api_key')
        if api_key != expected_api_key:
            return BaseApiResponse.error(message="Invalid or missing API key.", status=401)
        """Get in-house goods out for delivery"""
        try:
            vendor = request.env['res.partner'].sudo().browse(vendor_id)
            if not vendor.exists() or not vendor.is_vms_vendor:
                return BaseApiResponse.not_found('VMS Vendor not found')

            vendor_data = vendor.get_vms_vendor_data()
            inhouse_shipping_data = self._get_inhouse_shipping_data(vendor_data)
            return BaseApiResponse.success(data=inhouse_shipping_data)

        except Exception as e:
            _logger.error(f'Error in VMS in-house shipping endpoint: {str(e)}')
            return BaseApiResponse.error(message=str(e))

    # ============================================================================
    # TRANSACTION ENDPOINTS
    # ============================================================================

    @http.route('/api/vendors/<int:vendor_id>/vms/transactions/standard_all', type='http', auth='public', methods=['GET'], csrf=False)
    def vms_transactions_standard_all(self, vendor_id):
        api_key = request.httprequest.headers.get('X-API-KEY')
        expected_api_key = request.env['ir.config_parameter'].sudo().get_param('mataa_order_management.api_key')
        if api_key != expected_api_key:
            return BaseApiResponse.error(message="Invalid or missing API key.", status=401)
        """Get all daily order POs"""
        try:
            vendor = request.env['res.partner'].sudo().browse(vendor_id)
            if not vendor.exists() or not vendor.is_vms_vendor:
                return BaseApiResponse.not_found('VMS Vendor not found')

            vendor_data = vendor.get_vms_vendor_data()
            transactions_data = self._get_standard_transactions_data(vendor_data)
            return BaseApiResponse.success(data=transactions_data)

        except Exception as e:
            _logger.error(f'Error in VMS standard transactions endpoint: {str(e)}')
            return BaseApiResponse.error(message=str(e))

    @http.route('/api/vendors/<int:vendor_id>/vms/transactions/in_house_all', type='http', auth='public', methods=['GET'], csrf=False)
    def vms_transactions_in_house_all(self, vendor_id):
        api_key = request.httprequest.headers.get('X-API-KEY')
        expected_api_key = request.env['ir.config_parameter'].sudo().get_param('mataa_order_management.api_key')
        if api_key != expected_api_key:
            return BaseApiResponse.error(message="Invalid or missing API key.", status=401)
        """Get all in-house POs"""
        try:
            vendor = request.env['res.partner'].sudo().browse(vendor_id)
            if not vendor.exists() or not vendor.is_vms_vendor:
                return BaseApiResponse.not_found('VMS Vendor not found')

            vendor_data = vendor.get_vms_vendor_data()
            transactions_data = self._get_inhouse_transactions_data(vendor_data)
            return BaseApiResponse.success(data=transactions_data)

        except Exception as e:
            _logger.error(f'Error in VMS in-house transactions endpoint: {str(e)}')
            return BaseApiResponse.error(message=str(e))

    # ============================================================================
    # OUTSTANDING & FINANCIAL ENDPOINTS
    # ============================================================================

    @http.route('/api/vendors/<int:vendor_id>/vms/outstanding/standard', type='http', auth='public', methods=['GET'], csrf=False)
    def vms_outstanding_standard(self, vendor_id):
        api_key = request.httprequest.headers.get('X-API-KEY')
        expected_api_key = request.env['ir.config_parameter'].sudo().get_param('mataa_order_management.api_key')
        if api_key != expected_api_key:
            return BaseApiResponse.error(message="Invalid or missing API key.", status=401)
        """Get unpaid bills/refunds for standard vendor"""
        try:
            vendor = request.env['res.partner'].sudo().browse(vendor_id)
            if not vendor.exists() or not vendor.is_vms_vendor:
                return BaseApiResponse.not_found('VMS Vendor not found')

            vendor_data = vendor.get_vms_vendor_data()
            outstanding_data = self._get_standard_outstanding_data(vendor_data)
            return BaseApiResponse.success(data=outstanding_data)

        except Exception as e:
            _logger.error(f'Error in VMS standard outstanding endpoint: {str(e)}')
            return BaseApiResponse.error(message=str(e))

    @http.route('/api/vendors/<int:vendor_id>/vms/outstanding/in_house', type='http', auth='public', methods=['GET'], csrf=False)
    def vms_outstanding_in_house(self, vendor_id):
        api_key = request.httprequest.headers.get('X-API-KEY')
        expected_api_key = request.env['ir.config_parameter'].sudo().get_param('mataa_order_management.api_key')
        if api_key != expected_api_key:
            return BaseApiResponse.error(message="Invalid or missing API key.", status=401)
        """Get unpaid in-house clearances"""
        try:
            vendor = request.env['res.partner'].sudo().browse(vendor_id)
            if not vendor.exists() or not vendor.is_vms_vendor:
                return BaseApiResponse.not_found('VMS Vendor not found')

            vendor_data = vendor.get_vms_vendor_data()
            outstanding_data = self._get_inhouse_outstanding_data(vendor_data)
            return BaseApiResponse.success(data=outstanding_data)

        except Exception as e:
            _logger.error(f'Error in VMS in-house outstanding endpoint: {str(e)}')
            return BaseApiResponse.error(message=str(e))

    @http.route('/api/vendors/<int:vendor_id>/vms/payments', type='http', auth='public', methods=['GET'], csrf=False)
    def vms_payments(self, vendor_id):
        api_key = request.httprequest.headers.get('X-API-KEY')
        expected_api_key = request.env['ir.config_parameter'].sudo().get_param('mataa_order_management.api_key')
        if api_key != expected_api_key:
            return BaseApiResponse.error(message="Invalid or missing API key.", status=401)
        """Get all payments for the vendor"""
        try:
            vendor = request.env['res.partner'].sudo().browse(vendor_id)
            if not vendor.exists() or not vendor.is_vms_vendor:
                return BaseApiResponse.not_found('VMS Vendor not found')

            vendor_data = vendor.get_vms_vendor_data()
            payments_data = self._get_payments_data(vendor_data)
            return BaseApiResponse.success(data=payments_data)

        except Exception as e:
            _logger.error(f'Error in VMS payments endpoint: {str(e)}')
            return BaseApiResponse.error(message=str(e))

    @http.route('/api/vendors/<int:vendor_id>/vms/bills', type='http', auth='public', methods=['GET'], csrf=False)
    def vms_bills(self, vendor_id):
        api_key = request.httprequest.headers.get('X-API-KEY')
        expected_api_key = request.env['ir.config_parameter'].sudo().get_param('mataa_order_management.api_key')
        if api_key != expected_api_key:
            return BaseApiResponse.error(message="Invalid or missing API key.", status=401)
        """Get all vendor bills and refunds"""
        try:
            vendor = request.env['res.partner'].sudo().browse(vendor_id)
            if not vendor.exists() or not vendor.is_vms_vendor:
                return BaseApiResponse.not_found('VMS Vendor not found')

            vendor_data = vendor.get_vms_vendor_data()
            bills_data = self._get_bills_data(vendor_data)
            return BaseApiResponse.success(data=bills_data)

        except Exception as e:
            _logger.error(f'Error in VMS bills endpoint: {str(e)}')
            return BaseApiResponse.error(message=str(e))

    # ============================================================================
    # ATTACHMENT ENDPOINT
    # ============================================================================

    @http.route('/api/vendors/<int:vendor_id>/vms/blanket_order/<int:bo_id>/attachment', type='http', auth='public', methods=['POST'], csrf=False)
    def vms_blanket_order_attachment(self, vendor_id, bo_id):
        api_key = request.httprequest.headers.get('X-API-KEY')
        expected_api_key = request.env['ir.config_parameter'].sudo().get_param('mataa_order_management.api_key')
        if api_key != expected_api_key:
            return BaseApiResponse.error(message="Invalid or missing API key.", status=401)
        """Attach file to blanket order"""
        try:
            vendor = request.env['res.partner'].sudo().browse(vendor_id)
            if not vendor.exists() or not vendor.is_vms_vendor:
                return BaseApiResponse.not_found('VMS Vendor not found')
            
            vendor_data = vendor.get_vms_vendor_data()

            # Get blanket order
            blanket_order = request.env['purchase.requisition'].sudo().search([
                ('id', '=', bo_id),
                ('vendor_id', 'in', self._get_related_vendor_ids(vendor_data))
            ], limit=1)

            if not blanket_order:
                return BaseApiResponse.not_found('Blanket Order not found for this vendor')

            # Handle file upload
            if 'file' not in request.httprequest.files:
                return BaseApiResponse.error(message='No file provided')

            file_obj = request.httprequest.files['file']
            if not file_obj.filename:
                return BaseApiResponse.error(message='Invalid file')

            # Create attachment
            attachment = self._create_attachment(file_obj, blanket_order)

            return BaseApiResponse.success(
                data={'attachment_id': attachment.id},
                message='File attached successfully'
            )

        except Exception as e:
            _logger.error(f'Error in VMS blanket order attachment endpoint: {str(e)}')
            return BaseApiResponse.error(message=str(e))

    # ============================================================================
    # HELPER METHODS
    # ============================================================================

    def _get_related_vendor_ids(self, vendor_data):
        """Get all related vendor IDs"""
        vendor_ids = [vendor_data['id']]

        if vendor_data['vendor_type'] == 'standard':
            vendor_ids.extend(vendor_data['in_house_vendor_ids'])
        elif vendor_data['vendor_type'] == 'in_house' and vendor_data['standard_vendor_id']:
            vendor_ids.append(vendor_data['standard_vendor_id'])

        return vendor_ids

    def _get_vendor_summary(self, vendor_id):
        """Get vendor summary information"""
        vendor = request.env['res.partner'].sudo().browse(vendor_id)
        vendor_data = vendor.get_vms_vendor_data()
        related_ids = self._get_related_vendor_ids(vendor_data)

        # Count POs
        po_count = request.env['purchase.order'].sudo().search_count([
            ('partner_id', 'in', related_ids)
        ])

        # Count bills
        bill_count = request.env['account.move'].sudo().search_count([
            ('partner_id', 'in', related_ids),
            ('move_type', 'in', ['in_invoice', 'in_refund'])
        ])

        # Count payments
        payment_count = request.env['account.payment'].sudo().search_count([
            ('partner_id', 'in', related_ids),
            ('payment_type', '=', 'outbound')
        ])

        return {
            'po_count': po_count,
            'bill_count': bill_count,
            'payment_count': payment_count,
        }

    def _get_standard_stock_data(self, vendor_data):
        """Get standard stock data"""
        vendor_ids = self._get_related_vendor_ids(vendor_data)

        # Get stock moves for today
        today = fields.Date.today()
        stock_moves = request.env['stock.move'].sudo().search([
            ('purchase_line_id.order_id.partner_id', 'in', vendor_ids),
            ('picking_id.picking_type_code', '=', 'incoming'),
            ('date', '>=', today),
            ('state', 'in', ['assigned', 'partially_available', 'done'])
        ])

        stock_data = []
        for move in stock_moves:
            stock_data.append({
                'product_id': move.product_id.id,
                'product_name': move.product_id.name,
                'product_code': move.product_id.default_code,
                'quantity': move.product_uom_qty,
                'received_qty': move.quantity_done,
                'date': move.date.isoformat(),
                'state': move.state,
            })

        return stock_data

    def _get_return_stock_data(self, vendor_data):
        """Get return stock data"""
        vendor_ids = self._get_related_vendor_ids(vendor_data)

        # Get return stock moves
        return_moves = request.env['stock.move'].sudo().search([
            ('purchase_line_id.order_id.partner_id', 'in', vendor_ids),
            ('picking_id.picking_type_code', '=', 'incoming'),
            ('state', '=', 'done'),
            ('picking_id.is_return', '=', True)
        ])

        return_data = []
        for move in return_moves:
            return_data.append({
                'product_id': move.product_id.id,
                'product_name': move.product_id.name,
                'product_code': move.product_id.default_code,
                'return_qty': move.quantity_done,
                'return_date': move.date.isoformat(),
                'picking_name': move.picking_id.name,
            })

        return return_data

    def _get_inhouse_stock_data(self, vendor_data):
        """Get in-house stock data"""
        vendor_ids = self._get_related_vendor_ids(vendor_data)

        # Get in-house stock
        inhouse_products = request.env['product.product'].sudo().search([
            ('seller_ids.partner_id', 'in', vendor_ids),
            ('qty_available', '>', 0)
        ])

        inhouse_data = []
        for product in inhouse_products:
            inhouse_data.append({
                'product_id': product.id,
                'product_name': product.name,
                'product_code': product.default_code,
                'available_qty': product.qty_available,
                'standard_price': product.standard_price,
                'total_value': product.qty_available * product.standard_price,
            })

        return inhouse_data

    def _get_standard_shipping_data(self, vendor_data):
        """Get standard shipping data"""
        vendor_ids = self._get_related_vendor_ids(vendor_data)

        # Get shipping stock moves
        shipping_moves = request.env['stock.move'].sudo().search([
            ('purchase_line_id.order_id.partner_id', 'in', vendor_ids),
            ('picking_id.picking_type_code', '=', 'outgoing'),
            ('state', 'in', ['assigned', 'partially_available'])
        ])

        shipping_data = []
        for move in shipping_moves:
            shipping_data.append({
                'product_id': move.product_id.id,
                'product_name': move.product_id.name,
                'product_code': move.product_id.default_code,
                'shipping_qty': move.product_uom_qty,
                'shipping_date': move.date.isoformat(),
                'destination': move.picking_id.partner_id.name if move.picking_id.partner_id else 'N/A',
            })

        return shipping_data

    def _get_inhouse_shipping_data(self, vendor_data):
        """Get in-house shipping data"""
        vendor_ids = self._get_related_vendor_ids(vendor_data)

        # Get in-house shipping moves
        inhouse_shipping = request.env['stock.move'].sudo().search([
            ('purchase_line_id.order_id.partner_id', 'in', vendor_ids),
            ('picking_id.picking_type_code', '=', 'outgoing'),
            ('state', 'in', ['assigned', 'partially_available']),
            ('picking_id.location_id.usage', '=', 'internal')
        ])

        inhouse_shipping_data = []
        for move in inhouse_shipping:
            inhouse_shipping_data.append({
                'product_id': move.product_id.id,
                'product_name': move.product_id.name,
                'product_code': move.product_id.default_code,
                'shipping_qty': move.product_uom_qty,
                'shipping_date': move.date.isoformat(),
                'source_location': move.picking_id.location_id.name,
                'destination': move.picking_id.location_dest_id.name,
            })

        return inhouse_shipping_data

    def _get_standard_transactions_data(self, vendor_data):
        """Get standard transactions data"""
        vendor_ids = self._get_related_vendor_ids(vendor_data)

        # Get POs
        pos = request.env['purchase.order'].sudo().search([
            ('partner_id', 'in', vendor_ids),
            ('state', 'in', ['draft', 'sent', 'to approve', 'purchase', 'done'])
        ])

        transactions_data = []
        for po in pos:
            transactions_data.append(po.get_vms_po_summary())

        return transactions_data

    def _get_inhouse_transactions_data(self, vendor_data):
        """Get in-house transactions data"""
        vendor_ids = self._get_related_vendor_ids(vendor_data)

        # Get in-house POs (not linked to a sales order)
        inhouse_pos = request.env['purchase.order'].sudo().search([
            ('partner_id', 'in', vendor_ids),
            ('state', 'in', ['draft', 'sent', 'to approve', 'purchase', 'done']),
            ('sale_order_id', '=', False)
        ])

        transactions_data = []
        for po in inhouse_pos:
            transactions_data.append(po.get_vms_po_summary())

        return transactions_data

    def _get_standard_outstanding_data(self, vendor_data):
        """Get standard outstanding data"""
        vendor_ids = self._get_related_vendor_ids(vendor_data)

        # Get unpaid bills
        unpaid_bills = request.env['account.move'].sudo().search([
            ('partner_id', 'in', vendor_ids),
            ('move_type', 'in', ['in_invoice', 'in_refund']),
            ('state', '=', 'posted'),
            ('payment_state', '!=', 'paid')
        ])

        outstanding_data = []
        for bill in unpaid_bills:
            outstanding_data.append({
                'id': bill.id,
                'name': bill.name,
                'ref': bill.ref,
                'date': bill.invoice_date.isoformat() if bill.invoice_date else None,
                'amount_total': bill.amount_total,
                'amount_residual': bill.amount_residual,
                'move_type': bill.move_type,
            })

        return outstanding_data

    def _get_inhouse_outstanding_data(self, vendor_data):
        """Get in-house outstanding data based on unpaid clearance journal entries."""
        vendor_ids = self._get_related_vendor_ids(vendor_data)

        # Get the clearance journal from settings
        clearance_journal_id = request.env['ir.config_parameter'].sudo().get_param('mataa_vms_integration.vendor_clearance_journal_id')
        if not clearance_journal_id:
            return []  # Or handle as an error

        # Find unpaid/partially paid clearance journal entries
        clearance_moves = request.env['account.move'].sudo().search([
            ('journal_id', '=', int(clearance_journal_id)),
            ('line_ids.partner_id', 'in', vendor_ids),
            ('state', '=', 'posted'),
            ('amount_residual', '!=', 0)
        ])

        outstanding_data = []
        for move in clearance_moves:
            outstanding_data.append({
                'id': move.id,
                'name': move.name,
                'ref': move.ref,
                'date': move.date.isoformat(),
                'amount_total': move.amount_total,
                'amount_residual': move.amount_residual,
                'type': 'clearance',
            })

        return outstanding_data

    def _get_payments_data(self, vendor_data):
        """Get payments data"""
        vendor_ids = self._get_related_vendor_ids(vendor_data)

        # Get payments
        payments = request.env['account.payment'].sudo().search([
            ('partner_id', 'in', vendor_ids),
            ('payment_type', '=', 'outbound'),
            ('state', '=', 'posted')
        ])

        payments_data = []
        for payment in payments:
            payments_data.append({
                'id': payment.id,
                'name': payment.name,
                'date': payment.date.isoformat(),
                'amount': payment.amount,
                'payment_method': payment.payment_method_id.name,
                'ref': payment.ref,
            })

        return payments_data

    def _get_bills_data(self, vendor_data):
        """Get bills data"""
        vendor_ids = self._get_related_vendor_ids(vendor_data)

        # Get bills and refunds
        bills = request.env['account.move'].sudo().search([
            ('partner_id', 'in', vendor_ids),
            ('move_type', 'in', ['in_invoice', 'in_refund']),
            ('state', '=', 'posted')
        ])

        bills_data = []
        for bill in bills:
            bills_data.append({
                'id': bill.id,
                'name': bill.name,
                'ref': bill.ref,
                'date': bill.invoice_date.isoformat() if bill.invoice_date else None,
                'amount_total': bill.amount_total,
                'amount_residual': bill.amount_residual,
                'move_type': bill.move_type,
                'payment_state': bill.payment_state,
            })

        return bills_data

    def _create_attachment(self, file_obj, blanket_order):
        """Create attachment for blanket order"""
        try:
            # Read file content
            file_content = file_obj.read()
            file_name = file_obj.filename

            # Create attachment
            attachment = request.env['ir.attachment'].sudo().create({
                'name': file_name,
                'datas': file_content.encode('base64'),
                'res_model': 'purchase.requisition',
                'res_id': blanket_order.id,
                'mimetype': file_obj.content_type or 'application/octet-stream',
            })

            return attachment

        except Exception as e:
            _logger.error(f'Error creating attachment: {str(e)}')
            raise e
