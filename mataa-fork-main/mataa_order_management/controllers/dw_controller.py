from odoo import http
from odoo.http import request
from odoo.addons.mataa_base.controllers.common.BaseApiResponse import BaseApiResponse
import datetime

class DWController(http.Controller):

    @http.route('/api/dw/bills/<int:time_delta>', type='http', auth='public', methods=['GET'], csrf=False)
    def get_vendor_bills(self, time_delta):
        api_key = request.httprequest.headers.get('X-API-KEY')
        expected_api_key = request.env['ir.config_parameter'].sudo().get_param('mataa_order_management.api_key')
        if api_key != expected_api_key:
            return BaseApiResponse.error(message="Invalid or missing API key.", status=401)
        
        bills = request.env['account.move'].sudo().search([
            ("date", ">=", (datetime.date.today() - datetime.timedelta(days=time_delta)).strftime("%Y-%m-%d")),
            "|", "|",
            ("partner_id", "ilike", "ads"),
            ("partner_id", "ilike", "google"),
            ("partner_id", "ilike", "تسويق")
        ])


        bills_data = []
        for bill in bills:
            bills_data.append({
                "invoice_id": bill.id,
                "name": bill.name,
                "invoice_number": bill.ref,
                "state": bill.state,
                "partner_name": bill.invoice_partner_display_name,
                "payment_status": bill.payment_state,
                "accounting_date": bill.date.isoformat(),
                "total_amount": bill.amount_total,
                "total_amount_signed": bill.amount_total_signed,
                "total_quantity": bill.total_quantity,
                "activities": [activity.name for activity in bill.activity_ids] if bill.activity_ids else None,
                "bill_date": bill.invoice_date.isoformat() if bill.invoice_date else None,
                "due_date": bill.invoice_date_due.isoformat() if bill.invoice_date_due else None,
            })
        return BaseApiResponse.success(data=bills_data)


    @http.route('/api/dw/bills/month', type='http', auth='public', methods=['GET'], csrf=False)
    def get_vendor_bills_month(self):
        api_key = request.httprequest.headers.get('X-API-KEY')
        expected_api_key = request.env['ir.config_parameter'].sudo().get_param('mataa_order_management.api_key')
        if api_key != expected_api_key:
            return BaseApiResponse.error(message="Invalid or missing API key.", status=401)
        
        today = datetime.date.today()
        start_date = today.replace(day=1)
        next_month_start = (start_date + datetime.timedelta(days=32)).replace(day=1)
        
        bills = request.env['account.move'].sudo().search([
            ("date", ">=", start_date.strftime("%Y-%m-%d")),
            ("date", "<", next_month_start.strftime("%Y-%m-%d")),
            "|", "|",
            ("partner_id", "ilike", "ads"),
            ("partner_id", "ilike", "google"),
            ("partner_id", "ilike", "تسويق")
        ])


        bills_data = []
        for bill in bills:
            bills_data.append({
                "invoice_id": bill.id,
                "name": bill.name,
                "invoice_number": bill.ref,
                "state": bill.state,
                "partner_name": bill.invoice_partner_display_name,
                "payment_status": bill.payment_state,
                "accounting_date": bill.date.isoformat(),
                "total_amount": bill.amount_total,
                "total_amount_signed": bill.amount_total_signed,
                "total_quantity": bill.total_quantity,
                "activities": [activity.name for activity in bill.activity_ids] if bill.activity_ids else None,
                "bill_date": bill.invoice_date.isoformat() if bill.invoice_date else None,
                "due_date": bill.invoice_date_due.isoformat() if bill.invoice_date_due else None,
            })
        return BaseApiResponse.success(data=bills_data)