# -*- coding: utf-8 -*-
{
    'name': "Mataa Base",
    'summary': "Mataa Base",
    'description': "Mataa Base",

    'author': "Websers",
    'website': "https://websers.odoo.com",
    'license': 'OPL-1',

    'category': 'Mataa',
    'version': '1.7',

    'depends': ['base', 'project', 'product_multiple_barcodes', 'product_brand', 'stock', 'mrp', 'website_sale' , "spreadsheet_dashboard"],

    'post_init_hook': 'reassign_spreadsheet_groups',

    'data': [
        'data/ir_action_data.xml',
        'data/dashboard_cron.xml',
        'security/ir.model.access.csv',
        'views/product_brand_view.xml',
        'views/res_partner_view.xml',
        'views/product_product_view.xml',
        'views/product_template_view.xml',
        'views/sale_order_view.xml',
        'views/project_task_views.xml',
        'views/stock_quant.xml',
    ],


    'installable': True,
    'application': False,

    'controllers': [
        'controllers/auth_controller.py',
        # 'controllers/example_controller.py',
    ],
}
