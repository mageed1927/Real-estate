from odoo import api, models
from odoo.exceptions import UserError


class CustomerService:

    @staticmethod
    def get_customer(env, mataa_id):
        """Get customer by name"""
        customer = env['res.partner'].search([
            ('mataa_id', '=', mataa_id),
            ('supplier_rank', '=', 0)
        ], limit=1)

        return customer

    @staticmethod
    def create_customer(env, mataa_id, customer_name, customer_email=None, street=None, street2=None, country_id=None, city=None, gender=None, phone=None, birthdate_date=None):
        """create customer"""
        customer = env['res.partner'].sudo().create({
            'mataa_id': mataa_id,
            'name': customer_name,
            'email': customer_email,
            'street': street,
            'street2': street2,
            'country_id': country_id,
            'city': city,
            'birthdate_date': birthdate_date,
            'gender': gender,
            'phone': phone,
            'is_company': False,
            'supplier_rank': 0,
            'customer_rank': 1
        })

        return customer

    @staticmethod
    def update_customer(env, mataa_id, customer_name, customer_email=None, street=None, street2=None, country_id=None,
                        city=None, gender=None, phone=None, birthdate_date=None):
        """update customer"""
        customer = CustomerService.get_customer(env, mataa_id)
        customer.write({
            'name': customer_name or customer.name,
            'email': customer_email or customer.email,
            'street': street or customer.street,
            'street2': street2 or customer.street2,
            'country_id': country_id or customer.country_id,
            'city': city or customer.city,
            'birthdate_date': birthdate_date or customer.birthdate_date,
            'gender': gender or customer.gender,
            'phone': phone or customer.phone,
            'is_company': False,
            'supplier_rank': 0,
            'customer_rank': 1
        })

        return customer

