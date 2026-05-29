{
    'name': 'Mataa Inventory',
    'version': '1.0',
    'category': 'Inventory/Inventory',
    'author': 'Ahmed Barka',
    'depends': ['stock', 'stock_barcode'],
    'data': [
        'views/res_config_settings_view.xml',
        'views/stock_quant_relocate_view.xml',
        'views/stock_quant_barcode_pagination_views.xml'
    ],
    'assets': {
        'web.assets_backend': [
            'mataa_inventory/static/src/js/barcode_model_patch.js',
            'mataa_inventory/static/src/js/barcode_pagination_action.js',
            'mataa_inventory/static/src/xml/barcode_template_extensions.xml',
            'mataa_inventory/static/src/xml/barcode_pagination_button.xml',
        ],
    },
    'installable': True,
    'application': False,
    'license': 'OEEL-1',
}
