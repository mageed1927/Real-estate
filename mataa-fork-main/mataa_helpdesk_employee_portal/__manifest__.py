# -*- coding: utf-8 -*-
{
    'name': "Mataa Helpdesk Employee Portal",
    'summary': "Adds a helpdesk portal for employees",
    'description': """
        This module provides a dedicated portal for employees to interact with the helpdesk system.
    """,

    'author': "Websers",
    'website': "https://websers.odoo.com",
    'license': 'OPL-1',

    'category': 'Mataa',
    'version': '1.7',

    # any module necessary for this one to work correctly
    'depends': ['mataa_base', 'helpdesk', 'portal', 'website', 'hr', ],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'views/helpdesk_portal_templates.xml',
        'views/helpdesk_ticket_views.xml',
    ],

    'installable': True,
    'application': True,
}