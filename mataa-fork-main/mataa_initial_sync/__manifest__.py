# -*- coding: utf-8 -*-
{
    'name': "Mataa Initial Sync",
    'summary': "Mataa Initial Sync",
    'description': "Mataa Initial Sync",

    'author': "Websers",
    'website': "https://websers.odoo.com",
    'license': 'OPL-1',

    'category': 'Mataa',
    'version': '1.0',

    'depends': ['mataa_base', 'mataa_external_sync', 'mataa_product_management'],

    'data': [
        'security/ir.model.access.csv',
        # 'views/example_view.xml',
        'views/presync_main_view.xml',
        'views/presync_categories_wizard_view.xml',
        'views/presync_attributes_wizard_view.xml',
        'views/presync_vendors_wizard_view.xml',
        'views/presync_customers_wizard_view.xml',
        'views/presync_products_wizard_view.xml',
        'views/presync_variants_wizard_view.xml',
        'views/presync_brands_wizard_view.xml',
    ],

    'installable': True,
    'application': True,

    'controllers': [
        # 'controllers/example_controller.py'
    ],
}

