from odoo import models, fields, api, _
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = "sale.order"

    dms_shipment_status = fields.Selection([
        ('pending', 'قيد الانتظار'),
        ('draft', 'مسودة'),
        ('shipping_request', 'طلب شحن'),
        ('in_warehouse', 'في المخزن'),
        ('on_delivery', 'قيد التوصيل'),
        ('delivered', 'تم التسليم'),
        ('partially_delivered', 'تم التسليم جزئياً'),
        ('fail_and_retry', 'اعادة محاولة تسليم'),
        ('out_returned', 'ارجاع للمرسل'),
        ('cancelled', 'ملغي'),
    ], string="DMS Shipment Status", tracking=True, copy=False,default='pending')

    def _get_dms_pickings(self):
        return self.picking_ids.filtered(
            lambda p: p.carrier_id and p.carrier_id.delivery_type == 'dms'
        )

    def action_view_dms_shipments(self):
        dms_pickings = self._get_dms_pickings()

        if not dms_pickings:
            raise UserError(_('No DMS shipments found for this order.'))

        action = self.env.ref('stock.action_picking_tree_all').read()[0]

        if len(dms_pickings) > 1:
            action['domain'] = [('id', 'in', dms_pickings.ids)]
        elif len(dms_pickings) == 1:
            action['views'] = [(self.env.ref('stock.view_picking_form').id, 'form')]
            action['res_id'] = dms_pickings.ids[0]
        else:
            action = {'type': 'ir.actions.act_window_close'}

        return action