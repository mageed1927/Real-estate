# -*- coding: utf-8 -*-
{
    'name': "Line Shipping",
    'summary': "Line Shipping",
    'description': "Line Shipping",

    'author': "Websers",
    'website': "https://websers.odoo.com",
    'license': 'OPL-1',

    'category': 'Mataa',
    'version': '1.1',

    'depends': ['base','mataa_base','mataa_base_delivery'],

    'data': [
        'views/delivery_line_view.xml',
        'views/mataa_city_view.xml',
        'views/res_config_settings_view.xml',
        'views/sale_order_view.xml',
    ],

}
