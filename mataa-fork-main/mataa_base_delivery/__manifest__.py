# -*- coding: utf-8 -*-
{
    'name': "Mataa Base Delivery",
    'summary': "Mataa Base Delivery",
    'description': "Mataa Base Delivery",

    'author': "Websers",
    'website': "https://websers.odoo.com",
    'license': 'OPL-1',

    'category': 'Mataa',
    'version': '1.2',

    'depends': ['base', 'contacts', 'sale', 'mataa_base','delivery', 'account'],

    'data': [
        'security/ir.model.access.csv',
        'views/delivery_carrier_view.xml',
        'views/mataa_city_view.xml',
        'views/res_partner_view.xml',
        'views/sale_order_view.xml',
    ],

}
