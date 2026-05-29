# -*- coding: utf-8 -*-
{
    'name': "Mataa Cashback Management",
    'summary': "A custom module for creating and managing automatic cashback programs.",
    'description': """
        This module allows creating cashback offers that automatically generate a wallet payment
        for the customer upon delivery confirmation.
    """,
    'author': "Mataa Team",
    'website': "https://mataaa.odoo.com/",
    'category': 'Sales/Sales',
    'version': '17.0.1.0.0',
    'depends': ['helpdesk','sale_management', 'stock', 'account', 'website_sale', 'product_brand','mataa_base','product_brand', 'mataa_order_management'],
    'data': [
        'security/ir.model.access.csv',
        'views/cashback_program_views.xml',
        'views/cashback_menus.xml',
        'views/sale_order_views.xml',
    ],
    'installable': True,
    'application': False,
}