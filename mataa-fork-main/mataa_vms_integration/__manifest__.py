# -*- coding: utf-8 -*-
{
    'name': "Mataa VMS Integration",
    'summary': "Vendor Management System Integration for Mataa",
    'description': """
        Vendor Management System (VMS) Integration Module for Mataa
        
        This module provides:
        - Unified vendor model linking in-house and standard vendor accounts
        - VMS API endpoints for vendor data access
        - Automated vendor clearance journal entries
        - Purchase order bill creation automation
        - Vendor balance and transaction tracking
    """,

    'author': "Websers",
    'website': "https://websers.odoo.com",
    'license': 'OPL-1',

    'category': 'Mataa',
    'version': '1.0',

    'depends': ['base', 'purchase', 'account', 'stock', 'mataa_base', 'mataa_order_management',
                'mataa_product_management'],

    'data': [
        'views/menu.xml',
        'views/res_partner_view.xml',
        'views/res_config_settings_view.xml',
        'views/sale_order_view.xml',
        # 'views/res_company_view.xml',

    ],

    'installable': True,
    'application': False,

    'controllers': [
        'controllers/vms_controller.py',
    ],
}
