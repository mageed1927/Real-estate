# -*- coding: utf-8 -*-
{
    'name': "Mataa Advanced Import",
    'summary': "Mataa Advanced Import",
    'description': "Mataa Advanced Import",

    'author': "Websers",
    'website': "https://websers.odoo.com",
    'license': 'OPL-1',

    'category': 'Mataa',
    'version': '1.0',

    'depends': ['mataa_base'],

    'data': [
        'security/ir.model.access.csv',
        # 'views/example_view.xml',
        'views/log_imports_views.xml',
        'views/import_main_view.xml',
        'views/import_variants_view.xml',
        'views/import_quick_view.xml',
        'views/res_config_settings_view.xml',
        'views/import_po_view.xml'
    ],

    'installable': True,
    'application': True,

    'controllers': [
        # 'controllers/example_controller.py'
    ],
}
