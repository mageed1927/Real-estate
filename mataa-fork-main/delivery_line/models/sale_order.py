# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = "sale.order"

    delivery_line_status = fields.Selection([
        ('PKR', 'طلب شحن'),
        ('PKM', 'قيد الإلتقاط'),
        ('PKD', 'تم الإلتقاط'),
        ('RJCT', 'مرفوضة'),
        ('RITS', 'في المخزن'),
        ('OTD', 'قيد التوصيل'),
        ('DTR', 'تم التسليم'),
        ('DEX', 'إعادة محاولة التسليم'),
        ('HTR', 'انتظار لإعادة التوصيل'),
        ('RTS', 'إرجاع للمرسل'),
        ('OTR', 'قيد الإرجاع'),
        ('RTRN', 'تم الإرجاع للمرسل'),
        ('BMR', 'وصلت إلى الفرع'),
        ('BMT', 'في الطريق إلى الفرع'),
        ('PKH', 'انتظار لإعادة الإلتقاط'),
        ('PRP', 'جاري التجهيز'),
        ('STD', 'قيد الإرسال للمنذوب'),
        ('RCV', 'إرجاع للمخزن'),
        ('PRPD', 'تم التجهيز'),
    ], string="LINE Shipment Status", tracking=True)