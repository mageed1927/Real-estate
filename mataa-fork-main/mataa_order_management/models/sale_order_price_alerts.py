# -*- coding: utf-8 -*-

from odoo import models, fields, api


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    price_below_cost_alert = fields.Html(
        string='Price Below Cost Alert',
        compute='_compute_price_below_cost_alert',
        readonly=True
    )

    def _get_comparison_price(self, product):
        """
        Fetches the last purchase price, or falls back to the product cost if not found.
        """
        last_purchase_line = self.env['purchase.order.line'].search([
            ('product_id', '=', product.id),
            ('order_id.state', 'in', ['purchase', 'done'])
        ], order='id desc', limit=1)

        if last_purchase_line and last_purchase_line.price_unit > 0:
            return (last_purchase_line.price_unit, 'purchase')
        else:
            return (product.standard_price, 'cost')

    @api.depends('order_line.product_id', 'order_line.price_unit', 'state')
    def _compute_price_below_cost_alert(self):
        for order in self:
            # # Show the alert only in the initial states of the sales order
            # if order.state not in ('draft', 'sent'):
            #     order.price_below_cost_alert = ''
            #     continue

            alert_lines = []
            for line in order.order_line:
                product = line.product_id
                if not product:
                    continue

                comparison_price, price_source = self._get_comparison_price(product)
                price = line.price_unit or 0.0

                if comparison_price > 0 and price < comparison_price:

                    discount_reason_text = ''
                    if product.last_discount_reason_id:
                        discount_reason_text = f' <span style="color:#28a745;">(سبب التخفيض: {product.last_discount_reason_id.name})</span>'

                    if price_source == 'purchase':
                        message = f'سعر البيع ({price:.2f}) أقل من آخر سعر شراء وهو {comparison_price:.2f}'
                    else:  # source is 'cost'
                        message = f'سعر البيع ({price:.2f}) أقل من التكلفة {comparison_price:.2f} (لعدم وجود سعر شراء سابق)'

                    alert_lines.append(f'<li><b>{product.display_name}</b>: {message}{discount_reason_text}</li>')

            if alert_lines:
                order.price_below_cost_alert = (
                        '<div style="background-color:#f8d7da; color:#721c24; padding:16px; '
                        'border-radius:6px; border:1px solid #f5c6cb; font-size:15px; margin-bottom:10px;">'
                        '<strong>⚠️ تحذير: المنتجات التالية سعر بيعها أقل من السعر المرجعي:</strong>'
                        '<ul style="margin-top:8px;">'
                        + ''.join(alert_lines) +
                        '</ul></div>'
                )
            else:
                order.price_below_cost_alert = ''