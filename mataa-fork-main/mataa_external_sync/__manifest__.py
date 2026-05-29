# -*- coding: utf-8 -*-
{
    'name': "Mataa External Sync",
    'summary': "Mataa External Sync",
    'description': "Mataa External Sync",

    'author': "Websers",
    'website': "https://websers.odoo.com",
    'license': 'OPL-1',

    'category': 'Mataa',
    'version': '1.1',

    'depends': ['base', 'mataa_base','product', 'mataa_product_management', 'website_sale', 'stock'],

    'data': [
        # security
        'security/ir.model.access.csv',

        # views
        'views/product_template_view.xml',
        'views/product_product_view.xml',
        'views/product_sync_view.xml',
        'views/product_public_category_view.xml',
        'views/product_brand_view.xml',
        'views/res_config_settings_view.xml',

        # cron
        'data/cron_job.xml',

        # wizard
        'wizard/filter_from_file_wizard.xml',
    ],

    'installable': True,
    'application': True,

    'controllers': [
        'controllers/variant_controller.py'
    ],
}

