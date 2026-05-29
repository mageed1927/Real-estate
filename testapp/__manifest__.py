# -*- coding: utf-8 -*-
{
    'name': "First almohamady odoo module app",

    'summary': """
        odoo test course """,


    'description': """
        the new odoo test app for sdad
    """,

    'author': "alMohamady",
    'website': "https://www.al-Mohamady.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/16.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Uncategorized',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base', 'mail'],

    # always loaded
    'data': [
        'security/security_views.xml',
        'security/ir.model.access.csv',
        'views/contacts_new_view.xml',
        'views/views.xml',
        'views/templates.xml',
        'reports/my_report.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
}
