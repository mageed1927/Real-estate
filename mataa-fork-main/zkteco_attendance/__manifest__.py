{
    'name': 'ZKTeco Attendance Sync',
    'version': '1.0',
    'summary': 'Sync attendance from ZKTeco fingerprint device to Odoo',
    'author': 'Husam',
    'depends': ['hr','mataa_base','hr_holidays'],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_cron.xml',
        'views/hr_employee_views.xml',
        'views/res_config_settings_views.xml',
        'views/hr_attendance_views.xml',
        'views/zkteco_punch_views.xml',
        'views/templates.xml',
        'wizard/zkteco_fetch_wizard_views.xml',
    ],
    'installable': True,
    'application': True,
}