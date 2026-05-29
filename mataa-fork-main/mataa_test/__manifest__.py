# -*- coding: utf-8 -*-
{
    'name': "Mataa Test",
    'summary': "Mataa Test",
    'description': "Mataa Test",

    'author': "Websers",
    'website': "https://websers.odoo.com",
    'license': 'OPL-1',

    'category': 'Mataa',
    'version': '1.0',

    'depends': ['base', 'mataa_base', 'purchase'],

    'data': [
        'security/ir.model.access.csv',
        # 'views/example_view.xml',
    ],


    'installable': True,
    'application': True,

    'controllers': [
        'controllers/example_controller.py'
        'controllers/vendor_controller.py'
    ],
}

