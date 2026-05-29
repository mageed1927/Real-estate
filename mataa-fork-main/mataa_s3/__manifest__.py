# -*- coding: utf-8 -*-
{
    'name': "Mataa S3",
    'summary': "Mataa S3",
    'description': "Mataa S3",

    'author': "Websers",
    'website': "https://websers.odoo.com",
    'license': 'OPL-1',

    'category': 'Mataa',
    'version': '1.0',

    'depends': ['base', 'mataa_base'],

    'data': [
        'security/ir.model.access.csv',
        # 'views/example_view.xml',
        'views/res_config_settings_view.xml',
    ],

    'installable': True,
    'application': True,

    'controllers': [
        # 'controllers/example_controller.py'
    ],
}

