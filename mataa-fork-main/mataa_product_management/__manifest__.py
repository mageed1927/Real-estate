# -*- coding: utf-8 -*-
{
    'name': "Mataa Product Management",
    'summary': "Mataa Product Management",
    'description': "Mataa Product Management",

    'author': "Websers",
    'website': "https://websers.odoo.com",
    'license': 'OPL-1',

    'category': 'Mataa',
    'version': '1.4',

    'depends': ['base', 'mataa_base','product', 'sale',  'purchase', 'website_sale', 'stock', 'stock_barcode', 'product_brand'],

    'data': [
        # security
        'security/ir.model.access.csv',
        'security/mataa_security.xml',

        'data/ir_action_data.xml',
        'data/decimal_accuracy_data.xml',
        'data/product_filter_alert_cron.xml',

        # 'views/example_view.xml',
        'views/product_template_view.xml',
        'views/product_product_view.xml',
        'views/product_attribute_view.xml',
        'views/product_seo_keywords_view.xml',
        'views/product_true_reference_view.xml',
        'views/product_supplier_info_view.xml',
        'views/res_config_settings_view.xml',
        'views/res_partner_view.xml',
        'views/vendor_credit_difference_tracker_view.xml',
        'views/product_brand_view.xml',
        'views/product_attribute_value_view.xml',
        'views/product_public_category_view.xml',
        'wizard/product_url_wizard_view.xml',
		'views/product_template_form.xml',
        'views/product_filter_alerts_view.xml',
],
    'assets': {
        'web.assets_backend': [
            'mataa_product_management/static/src/xml/systray.xml',
            'mataa_product_management/static/src/components/grouped_line.xml',
            'mataa_product_management/static/src/**/*.js',
        ],
    },
    'installable': True,
    'application': True,

    'controllers': [
        # 'controllers/example_controller.py'
    ],
}

