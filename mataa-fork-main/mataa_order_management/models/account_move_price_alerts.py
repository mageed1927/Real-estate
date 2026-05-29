# -*- coding: utf-8 -*-

from odoo import models, fields, api, _

class AccountMove(models.Model):
    _inherit = 'account.move'

    price_below_cost_alert = fields.Html(string='Price Below Cost Alert', compute='_compute_price_below_cost_alert')
    price_above_last_purchase_alert = fields.Html(string='Price Above Last Purchase Alert',
                                                  compute='_compute_price_above_last_purchase_alert')

    def _get_comparison_price(self, product):
        last_purchase_line = self.env['purchase.order.line'].search([
            ('product_id', '=', product.id),
            ('order_id.state', 'in', ['purchase', 'done'])
        ], order='id desc', limit=1)

        if last_purchase_line and last_purchase_line.price_unit > 0:
            return (last_purchase_line.price_unit, 'purchase')
        else:
            return (product.standard_price, 'cost')

    # Helper function to get ONLY the last purchase price (no fallback to cost)
    def _get_last_purchase_price_only(self, product):
        last_purchase_line = self.env['purchase.order.line'].search([
            ('product_id', '=', product.id),
            ('order_id.state', 'in', ['purchase', 'done'])
        ], order='id desc', limit=1)
        return last_purchase_line.price_unit if last_purchase_line else 0.0

    # activity function
    @api.model
    def create_activity_for_low_margin_invoice(self, invoice):
        # Get the default review user from config settings
        param_user_id = self.env['ir.config_parameter'].sudo().get_param(
            'mataa_order_management.default_user_review_order_price_id')
        review_user = self.env['res.users'].browse(int(param_user_id)) if param_user_id else None
        if not review_user: return
        trigger_activity = False
        for line in invoice.invoice_line_ids:
            if not line.product_id: continue
            comparison_price, _ = self._get_comparison_price(line.product_id)
            if comparison_price > 0 and line.price_unit < comparison_price:
                trigger_activity = True
                break
        if not trigger_activity: return
        activity_note = (
            f"تحتوي الفاتورة {invoice.name} على منتجات بسعر أقل من السعر المرجعي (آخر شراء أو التكلفة). يرجى مراجعة التفاصيل.")
        self.env['mail.activity'].create({
            'res_model_id': self.env['ir.model']._get_id('account.move'),
            'res_id': invoice.id,
            'activity_type_id': self.env.ref('mail.mail_activity_data_todo').id,
            'summary': "⚠ راجع الفاتورة: السعر أقل من السعر المرجعي",
            'note': activity_note,
            'user_id': review_user.id,
            'date_deadline': fields.Date.context_today(invoice),
        })

    def action_post(self):
        res = super().action_post()
        for invoice in self:
            if invoice.move_type in ['out_invoice', 'in_invoice']:
                self.create_activity_for_low_margin_invoice(invoice)
        return res



    @api.depends('invoice_line_ids.product_id', 'invoice_line_ids.price_unit', 'move_type')
    def _compute_price_below_cost_alert(self):
        for move in self:
            alert_lines = []

            if move.move_type in ('out_invoice', 'out_refund', 'in_invoice', 'in_refund'):
                for line in move.invoice_line_ids:
                    product = line.product_id
                    if not product: continue
                    comparison_price, price_source = self._get_comparison_price(product)
                    price = line.price_unit or 0.0
                    if comparison_price > 0 and price < comparison_price:

                        discount_reason_text = ''
                        if product.last_discount_reason_id:
                            discount_reason_text = f' <span style="color:#28a745;">(سبب التخفيض: {product.last_discount_reason_id.name})</span>'


                        doc_type_string = "البيع" if move.move_type in ('out_invoice', 'out_refund') else "الشراء"
                        if price_source == 'purchase':
                            message = f'سعر {doc_type_string} ({price:.2f}) أقل من آخر سعر شراء وهو {comparison_price:.2f}'
                        else:
                            message = f'سعر {doc_type_string} ({price:.2f}) أقل من التكلفة {comparison_price:.2f} (لعدم وجود سعر شراء سابق)'

                        alert_lines.append(f'<li><b>{product.display_name}</b>: {message}{discount_reason_text}</li>')

            if alert_lines:
                move.price_below_cost_alert = (
                        '<div style="background-color:#f8d7da; color:#721c24; padding:16px; border-radius:6px; border:1px solid #f5c6cb; font-size:15px; margin-bottom:10px;">'
                        '<strong>⚠️ تحذير: المنتجات التالية سعرها أقل من السعر المرجعي:</strong>'
                        '<ul style="margin-top:8px;">' + ''.join(alert_lines) + '</ul></div>')
            else:
                move.price_below_cost_alert = ''

    # Compute method for the yellow alert
    @api.depends('invoice_line_ids.product_id', 'invoice_line_ids.price_unit', 'move_type')
    def _compute_price_above_last_purchase_alert(self):
        for move in self:
            alert_lines = []
            # This alert only runs on Vendor Bills
            if move.move_type in ('in_invoice', 'in_refund'):
                for line in move.invoice_line_ids:
                    product = line.product_id
                    if not product: continue

                    # only care about the last purchase price for this logic
                    last_purchase_price = self._get_last_purchase_price_only(product)
                    price = line.price_unit or 0.0

                    # Condition: Current purchase price is higher than the last one
                    if last_purchase_price > 0 and price > last_purchase_price:
                        message = f'سعر الشراء الحالي ({price:.2f}) أعلى من آخر سعر شراء وهو ({last_purchase_price:.2f})'
                        alert_lines.append(f'<li><b>{product.display_name}</b>: {message}</li>')

            if alert_lines:
                # Using yellow colors for this warning
                move.price_above_last_purchase_alert = (
                        '<div style="background-color:#fff3cd; color:#856404; padding:16px; border-radius:6px; border:1px solid #ffeeba; font-size:15px; margin-bottom:10px;">'
                        '<strong>🔔 تنبيه: تم شراء المنتجات التالية بسعر أعلى من المعتاد:</strong>'
                        '<ul style="margin-top:8px;">' + ''.join(alert_lines) + '</ul></div>')
            else:
                move.price_above_last_purchase_alert = ''