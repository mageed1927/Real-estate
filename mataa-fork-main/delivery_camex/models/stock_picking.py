# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.tools import Markup


class Picking(models.Model):
    _inherit = "stock.picking"

    camex_shipment_id = fields.Char(string="Camex Shipment ID", readonly=True, tracking=True)
    camex_shipment_trace_id = fields.Char(string="Camex Shipment traceId", readonly=True, tracking=True)
    camex_shipment_state = fields.Selection(
        [('-2', 'لم تُقبل من إدارة المخزون بعد'),
         ('0', 'تم الإدخال ولكن لم تُستقبل في المخزن بعد'),
         ('1', 'بدأ تجهيز الشحنة'),
         ('2', 'جاهزة من إدارة المخزون'),
         ('3', 'في المخزن'),
         ('4', 'تحويل للفرع'),
         ('5', 'نقل للزبون'),
         ('6', ' استلام زبون'),
         ('8', 'جاري الارجاع لفرع طرابلس'),
         ('9', 'في طريق العودة مع المندوب'),
         ('11', 'أُعيدت إلى العميل'),
         ('12', 'تم قبض القيمة'),
         ('16', 'أُلغيت'),
         ('18', 'تحويل الى مخزن النقطة الرئيسية'),
         ('19', 'أُعيدت إلى إدارة المخزون'),
         ('20', 'طلب تعديل')],
        string="Camex Shipment Status", tracking=True, copy=False)
    camex_number_of_items = fields.Integer(string="Camex Number Of Items", readonly=True, tracking=True)
    camex_number_of_returned_items = fields.Integer(string="Camex Number Of Returned Items", readonly=True,
                                                    tracking=True)
    camex_price = fields.Float(string="Camex Price", readonly=True, tracking=True)
    camex_delivered_with_price = fields.Float(string="Camex deliveredWithPrice", readonly=True, tracking=True)
    barcode_ref = fields.Char(string="Barcode Reference", compute="_compute_barcode_ref", store=True)

    @api.depends("name")
    def _compute_barcode_ref(self):
        for rec in self:
            rec.barcode_ref = rec.name  # or generate code128 if needed

    def _create_or_update_camex_batch(self):
        """Group all ready outgoing pickings for CAMEX into a batch."""
        Batch = self.env['stock.picking.batch']
        outgoing_type = self.env['stock.picking.type'].search([('code', '=', 'outgoing')], limit=1)

        ready_pickings = self.env['stock.picking'].search([
            ('state', '=', 'assigned'),
            ('carrier_id.delivery_type', '=', 'camex'),
            ('picking_type_id', '=', outgoing_type.id),
            ('batch_id', '=', None)
        ])

        if not ready_pickings:
            return False

        batch = Batch.search([
            ('state', '=', 'draft'),
            ('carrier_id.delivery_type', '=', 'camex')
        ], limit=1)

        if not batch:
            batch = Batch.create({
                'name': self.env['ir.sequence'].next_by_code('stock.picking.batch') or _('CAMEX Batch'),
                'user_id': self.env.uid,
                'picking_ids': [(6, 0, ready_pickings.ids)],
                'carrier_id': self.carrier_id.id,
                'company_id': self.company_id.id,
            })
        else:
            batch.write({'picking_ids': [(4, pid) for pid in ready_pickings.ids]})

        self.message_post(body=_("CAMEX Batch <b>%s</b> updated with ready outgoing moves.") % batch.name)
        return batch

    def _action_done(self):
        """
        This function is called when a picking is marked as done.
        change the mata_order_state to 'processing' when the OUT picking is done.
        """
        res = super(Picking, self)._action_done()
        for pick in self:
            if pick.picking_type_id.code == 'outgoing' and pick.sale_id:
                pick.sale_id.write({'mata_order_state': 'shipping'})
            if pick.picking_type_id.display_name == 'Mataa: Pack' and pick.carrier_id.delivery_type == 'camex':
                pick._create_or_update_camex_batch()
        return res

    def write(self, vals):
        res = super(Picking, self).write(vals)
        if 'camex_shipment_state' in vals:
            for pick in self:
                if not pick.sale_id:
                    continue

                so_id = pick.sale_id

                so_id.write({'camex_shipment_state': pick.camex_shipment_state})

                if 0 < pick.camex_number_of_returned_items < pick.camex_number_of_items:
                    config_param = self.env['ir.config_parameter'].sudo()
                    responsible_user_id_str = config_param.get_param('delivery_camex.camex_responsible_user_id')
                    responsible_user_id = int(responsible_user_id_str) if responsible_user_id_str else None


                    user_to_assign = responsible_user_id or so_id.user_id.id or self.env.ref('base.user_admin').id


                    summary = "تنبيه: استلام جزئي من Camex"
                    note = f"""
                                    <p>تم استلام شحنة بشكل جزئي بخصوص أمر البيع <b>{so_id.name}</b>.</p>
                                    <ul>
                                        <li><strong>إجمالي الأصناف:</strong> {pick.camex_number_of_items}</li>
                                        <li><strong>الأصناف المرتجعة:</strong> {pick.camex_number_of_returned_items}</li>
                                    </ul>
                                    <p>هذا التنبيه للعلم والمتابعة.</p>
                                    """


                    activity_model = self.env['mail.activity']
                    domain = [
                        ('res_model_id', '=', self.env.ref('sale.model_sale_order').id),
                        ('res_id', '=', so_id.id),
                        ('summary', '=', summary),
                        ('user_id', '=', user_to_assign),
                    ]

                    if not activity_model.search(domain, limit=1):
                        activity_model.create({
                            'res_model_id': self.env.ref('sale.model_sale_order').id,
                            'res_id': so_id.id,
                            'user_id': user_to_assign,
                            'activity_type_id': self.env.ref('mail.mail_activity_data_todo').id,
                            'summary': summary,
                            'note': Markup(note),
                        })

                shipping_price = so_id.get_shipping_price()

                shipment_price = so_id.get_shipment_price()

                pick_total_quantity_delivered = sum(pick.mapped('move_ids.quantity'))

                new_shipping_price = pick.camex_delivered_with_price - shipment_price + shipping_price if pick.camex_delivered_with_price > 0 else 0

                partially_flag = False
                finalize_order_flag = False

                # For 'Delivered' state
                if pick.camex_shipment_state == '6':
                    so_id.write({'mata_order_state': 'completed'})

                    if pick_total_quantity_delivered == pick.camex_number_of_items and pick.camex_number_of_returned_items == 0:
                        # TODO : review this piece of code , as it will always be false (code was indented)
                        # all_pickings = self.search([('sale_id', '=', pick.sale_id.id)])
                        # if all(p.camex_shipment_state == '6' for p in all_pickings):

                        if pick.camex_delivered_with_price != shipment_price:
                            finalize_order_flag = False
                            so_id.create_order_closing_activity()
                        else:
                            if not so_id.is_refund_order:
                                finalize_order_flag = True
                            else:
                                finalize_order_flag = False


                        # sol_ids = so_id.order_line.filtered(lambda line: line.is_delivery)
                        #
                        # if not so_id.is_refund_order:
                        #     finalize_order_flag = True
                        # else:
                        #     finalize_order_flag = False
                        #
                        # if new_shipping_price:
                        #     if new_shipping_price < shipping_price:
                        #         if sol_ids:
                        #             sol_ids[0].write({'price_unit': new_shipping_price})
                        #
                        #     elif new_shipping_price > shipping_price:
                        #         shipping_deviation_threshold = so_id.company_id.shipping_deviation_threshold
                        #
                        #         shipping_deviation = 0
                        #         if shipping_price > 0:
                        #             shipping_deviation = ((new_shipping_price - shipping_price) / shipping_price) * 100
                        #
                        #         if shipping_deviation > shipping_deviation_threshold:
                        #             finalize_order_flag = False
                        #             so_id.create_order_closing_activity()
                        #         else:
                        #             if sol_ids:
                        #                 sol_ids[0].write({'price_unit': new_shipping_price})

                        pick.sale_id.close_fully_delivered_order()
                    else:
                        partially_flag = True


                # For 'Returned' state
                elif pick.camex_shipment_state == '11':
                    # if pick_total_quantity_delivered == pick.camex_number_of_returned_items:
                    if pick.camex_number_of_returned_items == 0 and pick.camex_delivered_with_price == 0:
                        # TODO : review this piece of code , as it will always be false (code was indented)
                        # all_pickings = self.search([('sale_id', '=', pick.sale_id.id)])
                        # if all(p.camex_shipment_state == '11' for p in all_pickings):
                            # TODO - To Check: Unable to make any assumptions due to my lack of understanding of the request.

                        pick.sale_id.close_fully_returned_order()
                    else:
                        partially_flag = True

                if partially_flag:
                    so_id.close_partially_delivered_order()

                if finalize_order_flag:
                    so_id.finalize_mataa_order()
        return res
