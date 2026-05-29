{
    'name': 'Mataa Delivery System',
    'version': '17.0.1.0.0',
    'category': 'Inventory/Delivery',
    'summary': 'Integration with DMS delivery service for Mataa',
    'description': """
        This module integrates Odoo with DMS delivery service for Mataa system.
        Features:
        - Create shipments automatically when stock moves are confirmed
        - Track shipment status via webhooks
        - Calculate delivery costs based on zones
        - Full API integration with DMS service
    """,
    'author': 'Mataa Team',
    'website': 'https://www.mataa.com',
    'depends': [
        'delivery',
        'stock',
        'sale',
        'mataa_base',
        'delivery_line',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/delivery_dms_data.xml',
        'views/delivery_dms_view.xml',
        'views/mataa_city_view.xml',
		'views/sale_order_view.xml',
],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}