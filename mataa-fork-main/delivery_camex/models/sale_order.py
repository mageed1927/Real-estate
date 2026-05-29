# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = "sale.order"

    camex_area_name = fields.Char(string="Camex Area Name", related="mataa_city_id.camex_area_name")
    camex_shipment_state = fields.Selection(
        [('-2', 'لم تُقبل من إدارة المخزون بعد'),
         ('0', 'تم الإدخال ولكن لم تُستقبل في المخزن بعد'),
         ('1', 'بدأ تجهيز الشحنة'),
         ('2', 'جاهزة من إدارة المخزون'),
         ('3', 'في المخزن'),
         ('4', 'تحويل للفرع'),
         ('5', 'نقل للزبون'),
         ('6', 'استلام زبون'),
         ('8', 'جاري الارجاع لفرع طرابلس'),
         ('9', 'في طريق العودة مع المندوب'),
         ('11', 'أُعيدت إلى العميل'),
         ('12', 'تتم قبض القيمة'),
         ('16', 'أُلغيت'),
         ('18', 'تحويل الى مخزن النقطة الرئيسية'),
         ('19', 'أُعيدت إلى إدارة المخزون'),
         ('20', 'طلب تعديل')],
        string="Camex Shipment Status", tracking=True)
