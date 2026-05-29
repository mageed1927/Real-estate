from odoo import models, fields, api
from odoo.exceptions import ValidationError

class SaleLoyaltyCouponWizard(models.TransientModel):
    _inherit = 'sale.loyalty.coupon.wizard'

    coupon_code = fields.Char(required=False)

    option_type = fields.Selection([
        ('new', 'Add New Coupon'),
        ('existing', 'Add Existing Code')
    ], string="Option", required=True, default='existing')
    coupon_type = fields.Selection([
        ('free_shipping', 'Free Shipping'),
        ('fixed_discount', 'Fixed Discount'),
        ('percentage_discount', 'Percentage Discount')
    ], string="Coupon Type")
    discount_amount = fields.Float(string="Discount Amount")
    discount_percentage = fields.Float(string="Discount Percentage")

    def action_apply(self):
        self.ensure_one()
        sale_order = self.env['sale.order'].browse(self.env.context.get('active_id'))
        if self.option_type == 'new' and not self.coupon_code:
            self.coupon_code = f"AUTO-{fields.Datetime.now().strftime('%Y%m%d%H%M%S')}"
            if self.coupon_type == 'free_shipping':
                self.coupon_code = f"Free shipping-{fields.Datetime.now().strftime('%Y%m%d%H%M%S')}"
                for line in sale_order.order_line:
                    if line.product_id.type == 'service':
                        line.product_uom_qty = 0
                self._log_coupon_message(
                    sale_order,
                    self.coupon_code,
                    "تم ضبط كمية منتج الشحن إلى صفر للشحن المجاني."
                )
                return self._notify("Free Shipping Applied", " the shipping line have been set to zero quantity for free shipping.")

            elif self.coupon_type == 'fixed_discount':
                self.coupon_code = f"fixed amount-{fields.Datetime.now().strftime('%Y%m%d%H%M%S')}"
                if not self.discount_amount or self.discount_amount <= 0:
                    raise ValidationError("Please enter a positive discount amount.")

                product_lines = sale_order.order_line.filtered(lambda l: l.product_id.type != 'service')
                total = sum(sale_order.order_line.mapped('price_subtotal'))
                if not total:
                    raise ValidationError("No order lines to apply discount.")

                for line in product_lines:
                    proportion = line.price_subtotal / total
                    discount_value = proportion * self.discount_amount
                    line.price_unit -= discount_value / (line.product_uom_qty or 1.0)
                sale_order.write({
                    'coupon_applied': True,
                    'coupon_type': 'fixed_discount',
                    'discount_amount': self.discount_amount,
                    'discount_percentage': 0.0,
                })
                self._log_coupon_message(
                    sale_order,
                    self.coupon_code,
                    "تم توزيع خصم إجمالي بقيمة {:.2f} عبر منتجات الطلب.".format(self.discount_amount),
                )

                return self._notify("Fixed Discount Applied", f"A total discount of {self.discount_amount:.2f} was distributed across order lines.")

            elif self.coupon_type == 'percentage_discount':
                self.coupon_code = f"percentage_discount-{fields.Datetime.now().strftime('%Y%m%d%H%M%S')}"
                if not self.discount_percentage or self.discount_percentage <= 0:
                    raise ValidationError("Please enter a positive discount percentage.")

                product_lines = sale_order.order_line.filtered(lambda l: l.product_id.type != 'service')
                if not product_lines:
                    raise ValidationError("No product lines to apply discount (service products are skipped).")

                total = sum(product_lines.mapped('price_subtotal'))
                if not total:
                    raise ValidationError("No valid subtotal found on product lines.")

                total_discount = total * (self.discount_percentage / 100.0)

                for line in product_lines:
                    proportion = line.price_subtotal / total
                    discount_value = proportion * total_discount
                    line.price_unit -= discount_value / (line.product_uom_qty or 1.0)

                sale_order.write({
                    'coupon_applied': True,
                    'coupon_type': 'percentage_discount',
                    'discount_amount': 0.0,
                    'discount_percentage': self.discount_percentage,
                })

                self._log_coupon_message(
                    sale_order,
                    self.coupon_code,
                    "تم تطبيق خصم بنسبة {:.2f}% على جميع المنتجات.".format(self.discount_percentage),
                )

                return self._notify(
                    "Percentage Discount Applied",
                    f"A discount of {self.discount_percentage:.2f}% was applied to all products."
                )
        else:
            return super().action_apply()

    def _notify(self, title, message):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': title,
                'message': message,
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }

    def _log_coupon_message(self, sale_order, title, message):
        sale_order.message_post(
            body=f"اسم الكوبون: {title} //// {message}" ,
            message_type="comment",
            subtype_xmlid="mail.mt_note",
        )