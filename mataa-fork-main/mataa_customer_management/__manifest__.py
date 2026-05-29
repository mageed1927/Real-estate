# -*- coding: utf-8 -*-
{
    'name': "Mataa Customer Management",
    'summary': "Mataa Customer Management",
    'description': "Mataa Customer Management",

    'author': "Websers",
    'website': "https://websers.odoo.com",
    'license': 'OPL-1',

    'category': 'Mataa',
    'version': '1.1',

    'depends': ['base','mataa_base','account','sale'],

    'data': [
        'security/ir.model.access.csv',
        'views/res_partner_view.xml',
		'wizard/suspend_customer_wizard_view.xml'
    ],

    'controllers': [
        'controllers/customer_controller.py',
    ],
}

