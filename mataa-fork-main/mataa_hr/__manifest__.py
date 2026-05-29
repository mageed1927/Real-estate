# -*- coding: utf-8 -*-
{
    'name': 'Mataa HR',
    'summary': 'Mataa HR',
    'description': 'Mataa HR',

    'author': "Websers",
    'website': "https://websers.odoo.com",
    'license': 'OPL-1',

    'category': 'Mataa',
    'version': '1.0',

    'depends': ['hr_attendance','mataa_base', 'hr' , 'hr_payroll_account', 'hr_payroll','zkteco_attendance'],

    'data': [
        'security/hr_security.xml',
        'security/ir.model.access.csv',
        'wizard/hr_payslip_payment_wizard_views.xml',
        'views/precreation_employee_view.xml',
        'views/payroll_view.xml',
        'views/hr_employee_views.xml',
        'views/hr_contract_views.xml',
        'views/hr_payslip_views.xml',
        'views/hr_salary_rule_views.xml',
        'views/res_partner_views.xml',
        'views/res_config_settings_views.xml',
    ],
    'installable': True,
    'application': True,
}
