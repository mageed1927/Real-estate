# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class Picking(models.Model):
    _inherit = "stock.picking"

    line_shipment_id = fields.Char(string="Line Shipment ID", readonly=True, tracking=True)
    line_shipment_sate = fields.Selection([
        ('pending', 'Pending'),
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
    ], string="LINE Shipment State", tracking=True, default='pending')

    line_return_pieces = fields.Integer()
    
    def write(self,vals):
        res = super(Picking, self).write(vals)
        if 'line_shipment_sate' in vals.keys():
            for pick in self:
                if pick.line_shipment_sate == 'DTR':
                    pick.group_id.sale_id.close_mataa_order('fully_delivered')

                elif pick.line_shipment_sate == 'RTRN':
                    # Todo: need to uncomment when Line system return the returned pieces
                    # pick_pieces = int(sum(pick.move_ids.mapped('quantity')))
                    # if pick_pieces == pick.line_return_pieces:
                    pick.group_id.sale_id.close_mataa_order('fully_returned')
                else:
                    pick.group_id.sale_id.close_mataa_order('partially_delivered')

        return res