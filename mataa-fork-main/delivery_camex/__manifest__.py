# -*- coding: utf-8 -*-
{
    'name': "CAMEX Shipping",
    'summary': "CAMEX Shipping",
    'description': "CAMEX Shipping",

    'author': "Websers",
    'website': "https://websers.odoo.com",
    'license': 'OPL-1',

    'category': 'Mataa',
    'version': '1.2',

    'depends': ['base','mataa_base','mataa_base_delivery',"stock_picking_batch","stock_barcode","delivery",],

    'data': [
        'views/delivery_camex_view.xml',
        'views/mataa_city_view.xml',
        'views/res_config_settings_view.xml',
        'views/sale_order_view.xml'
],
    "assets": {
        "web.assets_backend": [
            'delivery_camex/static/src/js/barcode_picking_batch_model.js',
            'delivery_camex/static/src/js/main_patch.js',
            'delivery_camex/static/src/js/validate_exit_patch.js',

        ],
    }
}
