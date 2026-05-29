# -*- coding: utf-8 -*-

from odoo import http
from odoo.http import request
import json
from odoo.addons.mataa_base.controllers.common.BaseApiResponse import BaseApiResponse
from odoo.addons.mataa_base.controllers.utility.auth_required import auth_required
from datetime import datetime, timedelta


class CustomerController(http.Controller):

    # ------------- Wallet Handling -------------
    @http.route('/api/customers/<int:customer_id>/deposit', type='http', auth='public', methods=['POST'], csrf=False)
    def create_payment(self, customer_id):
        # TODO: Company
        company_id = request.env['res.company'].sudo().search([('id', '=', 1)], limit=1)
        data = json.loads(request.httprequest.data)
        try:
            journal_id = request.env['account.journal'].sudo().search([
                ('company_id', '=', company_id.id),
                ('code', '=', data.get('code')),
                ('type', 'in', ['bank', 'cash'])])
            if not journal_id:
                return BaseApiResponse.validation_error("No Bank/Cash journal found with this code")
            payment_id = request.env['account.payment'].sudo().create({
                'company_id': company_id.id,
                'partner_id': customer_id,
                'journal_id': journal_id.id,
                'amount': data.get('amount'),
                'ref': "إيداع في المحفظة",
                'payment_type': 'inbound',
                'partner_type': 'customer'
            })

            time_threshold = datetime.now() - timedelta(minutes=1)

            duplicate_payment = request.env['account.payment'].sudo().search([
                ('partner_id', '=', customer_id),
                ('amount', '=', data.get('amount')),
                ('state', '=', 'posted'),
                ('create_date', '>=', time_threshold),
                ('id', '!=', payment_id.id)
            ], limit=1)

            if not duplicate_payment:
                payment_id.sudo().with_context(no_create=True).action_post()
            else:
                payment_id.message_post(
                    body="تم إبقاء هذه الدفعة كمسودة (Draft) لأن النظام اكتشف دفعة مطابقة تم ترحيلها في نفس التوقيت.")

            return BaseApiResponse.created(data={
                'payment_id': payment_id.id,
                'journal_code': payment_id.journal_id.code,
                'amount': payment_id.amount,
                'ref': payment_id.ref,
                'payment_type': payment_id.payment_type,
                'partner_type': payment_id.partner_type,
                'state': payment_id.state,
            }, message='Payment created successfully')
        except Exception as e:
            return BaseApiResponse.error(message=str(e))

    @http.route('/api/customers/<int:customer_id>/wallet_balances', type='http', auth='public', methods=['GET'], csrf=False)
    def get_customers_wallet_balances(self, customer_id):
        # TODO: How to get multi customers

        partner_ids = request.env['res.partner'].sudo().search([('id', '=', customer_id)])

        wallet_balances = []
        for partner_id in partner_ids:
            wallet_balances.append({partner_id.id: partner_id.wallet_amount})

        return BaseApiResponse.success(data=wallet_balances)

    # ------------- Customer Management -------------

    # get customers
    @http.route('/api/customers', type='http', auth='public', methods=['GET'], csrf=False)
    def get_customers(self, page=1, page_size=10):
        page = int(page)
        page_size = int(page_size)
        offset = (page - 1) * page_size
        limit = page_size

        partner_ids = request.env['res.partner'].sudo().search([
            ('customer_rank', '>', 0)
        ], limit=limit, offset=offset)

        customers_data = []
        for partner_id in partner_ids:
            customers_data.append(self.get_customer_data(partner_id.id))

        total_count = len(partner_ids)
        meta = {
            'total_count': total_count,
            'page': page,
            'page_size': page_size,
            'total_pages': (total_count + page_size - 1) // page_size
        }
        return BaseApiResponse.success(data=customers_data, meta=meta)

    # get customers by ID
    @http.route('/api/customers/<int:customer_id>', type='http', auth='public', methods=['GET'], csrf=False)
    def get_customer(self, customer_id):

        partner_id = request.env['res.partner'].sudo().search([
            ('id', '=', customer_id),
            ('customer_rank', '>', 0)
        ])

        if not partner_id:
            return BaseApiResponse.not_found()

        return BaseApiResponse.success(data=self.get_customer_data(partner_id.id))

    # create customer
    @http.route('/api/customers', type='http', auth='public', methods=['POST'], csrf=False)
    def create_customer(self):
        data = json.loads(request.httprequest.data)
        try:
            birthdate_date = self.parse_date(data.get('birthdate_date'))
            gender = self.parse_gender(data.get('gender'))

            partner_id = request.env['res.partner'].sudo().with_context(pre_sync=True).create({
                'mataa_id': data.get('mataa_id'),
                'name': data.get('name'),
                'email': data.get('email'),
                'street': data.get('street'),
                'street2': data.get('street2'),
                'city': data.get('city'),
                'birthdate_date': birthdate_date,
                'gender': gender,
                'phone': data.get('phone'),
                'is_company': False,
                'supplier_rank': 0,
                'customer_rank': 1
            })

            customer_data = self.get_customer_data(partner_id.id)
            return BaseApiResponse.created(data=customer_data, message='Customer created successfully')
        except ValueError as e:
            return BaseApiResponse.error(message=str(e))
        except Exception as e:
            return BaseApiResponse.error(message=str(e))

    # update customer
    @http.route('/api/customers/<int:customer_id>', type='http', auth='public', methods=['PUT'], csrf=False)
    def update_customer(self, customer_id):
        data = json.loads(request.httprequest.data)

        partner_id = request.env['res.partner'].sudo().search([
            ('id', '=', customer_id),
            ('customer_rank', '>', 0)
        ])
        if not partner_id:
            return BaseApiResponse.not_found()

        try:
            birthdate_date = self.parse_date(data.get('birthdate_date'))

            partner_id.write({
                'name': data.get('name'),
                'email': data.get('email'),
                'street': data.get('street'),
                'street2': data.get('street2'),
                'city': data.get('city'),
                'birthdate_date': birthdate_date,
                'gender': data.get('gender'),
                'phone': data.get('phone')
            })

            customer_data = self.get_customer_data(partner_id.id)
            return BaseApiResponse.success(data=customer_data, message='Customer updated successfully')

        except ValueError as e:
            return BaseApiResponse.error(message=str(e))
        except Exception as e:
            return BaseApiResponse.error(message=str(e))

    # archive customer
    @http.route('/api/customers/<int:customer_id>/archive', type='http', auth='public', methods=['PUT'], csrf=False)
    def archive_customer(self, customer_id):
        try:
            partner_id = request.env['res.partner'].sudo().search([
                ('id', '=', customer_id),
                ('customer_rank', '>', 0)
            ])
            if not partner_id:
                return BaseApiResponse.not_found(message='Customer not found')
            partner_id.write({
                'active': False,
            })
            return BaseApiResponse.success(
                data=self.get_customer_data(partner_id.id),
                message='customer archived successfully')
        except Exception as e:
            return BaseApiResponse.error(message=str(e))


    # ------------- Utilities -------------

    def get_customer_data(self, partner_id):
        partner_id = request.env['res.partner'].sudo().browse(partner_id)
        customer_data = {
            'id': partner_id.id,
            'mataa_id': partner_id.mataa_id,
            'name': partner_id.name,
            'email': partner_id.email,
            'street': partner_id.street,
            'street2': partner_id.street2,
            'city': partner_id.city,
            'birthdate_date': partner_id.birthdate_date.strftime('%Y-%m-%d') if partner_id.birthdate_date else None,
            'gender': partner_id.gender,
            'phone': partner_id.phone,
            'state': 'enabled' if partner_id.active else 'disabled',
            'suspended': partner_id.is_suspended
            # 'is_deleted': partner_id.is_deleted
        }
        return customer_data
    def parse_date(self, date_string, date_format='%Y-%m-%d'):
        """
        Parses a date string to a datetime.date object if in the correct format.
        Returns None if date_string is None or an empty string.
        """
        if not date_string:
            return None
        try:
            return datetime.strptime(date_string, date_format).date()
        except ValueError:
            raise ValueError(f"Invalid date format for '{date_string}'. Expected format: {date_format}.")
    def parse_gender(self, gender):
        if gender in ['male', 'female']:
            return gender

        if gender == 'ذكر':
            return 'male'
        elif gender == 'أنثى':
            return 'female'
        else:
            return 'other'
