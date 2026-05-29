# -*- coding: utf-8 -*-
import random

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.tools import float_is_zero, format_amount, format_date, html_keep_url, is_html_empty
from datetime import datetime, timedelta

from odoo.exceptions import ValidationError
from ..services.vendor_notification_service import VendorNotificationService
from ..services.sale_order_service import SaleOrderSyncService
from ..services.wallet_service import WalletService
from ..services.vms_service import VMSService
from odoo.tools import float_compare,float_is_zero

import logging

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    amount_total_before_discount = fields.Monetary(
        string="Total Before Discount",
        compute="_compute_totals_before_after_discount",
        currency_field="currency_id",
        store=False,
    )
    amount_total_after_discount = fields.Monetary(
        string="Total After Discount",
        compute="_compute_totals_before_after_discount",
        currency_field="currency_id",
        store=False,
    )
    #fields for the cancel logic
    cancel_reason_ids = fields.Many2many(
        'order.cancel.reason',
        'sale_order_cancel_reason_rel',  # relation table name
        'order_id',
        'reason_id',
        string='Cancellation Reasons',
        copy=False,
    )


    cancel_note = fields.Text(
        string='Cancellation Note',
        copy=False,
    )

    time_taken = fields.Char(
        string='Time Taken',
        compute='_compute_time_taken',
        readonly=True,
    )

    @api.depends(
        'order_line.price_unit', 'order_line.product_uom_qty',
        'order_line.tax_id', 'order_line.discount',
        'order_line.display_type', 'order_line.is_reward_line',
        'order_line.is_delivery', 'order_line.is_downpayment',
        'amount_total'
    )
    def _compute_totals_before_after_discount(self):
        for order in self:
            total_before = 0.0
            currency = order.currency_id
            partner = order.partner_id
            for line in order.order_line:
                if line.display_type:
                    continue
                # Skip reward lines, coupon lines (fixed discounts), delivery lines, and downpayment lines
                if getattr(line, 'is_reward_line', False):
                    continue
                if getattr(line, 'is_coupon_line', False):
                    continue
                if getattr(line, 'is_delivery', False):
                    continue
                if getattr(line, 'is_downpayment', False):
                    continue
                taxes = line.tax_id.compute_all(
                    price_unit=line.price_unit,
                    currency=currency,
                    quantity=line.product_uom_qty,
                    product=line.product_id,
                    partner=partner,
                )

                total_before += taxes['total_included']

            order.amount_total_before_discount = currency.round(total_before)
            order.amount_total_after_discount = order.amount_total

    def _update_mataa_payment_amount(self):
        for order in self:
            if not order.mataa_payment_ids:
                continue
            currency = order.currency_id
            target_total = order.amount_total_after_discount
            current_total = sum(payment.amount for payment in order.mataa_payment_ids)
            difference = currency.round(abs(target_total - current_total))
            if float_compare(current_total, target_total, precision_rounding=order.currency_id.rounding) == 0:
                continue
            cod_payment = order.mataa_payment_ids.filtered(lambda p: p.code == 'cod')
            if not cod_payment:
                cod_payment = order.mataa_payment_ids.filtered(lambda p: p.code == 'CRDOD')
            if float_compare(target_total,current_total, precision_rounding=order.currency_id.rounding) > 0:
                if not cod_payment:
                    cod_payment = self.env['mataa.so.payment'].create({
                        'sale_order_id': order.id,
                        'code': 'cod',
                        'amount': 0,
                    })
                cod_payment.amount += difference
            else:
                if cod_payment and float_compare(cod_payment.amount, difference, precision_rounding=order.currency_id.rounding) > 0:
                    cod_payment.amount -= difference
                else:
                    if cod_payment:
                        difference -= cod_payment.amount
                        cod_payment.amount = 0
                    for payment in order.mataa_payment_ids:
                        if float_is_zero(payment.amount, precision_rounding=order.currency_id.rounding):
                            continue
                        if float_compare(payment.amount, difference, precision_rounding=order.currency_id.rounding) > 0:
                            payment.amount -= difference
                            if payment.code == 'walle':
                                self.env['switch.payment.method.wizard']._update_wallet_reservation_safely(order)
                            break
                        else:
                            difference -= payment.amount
                            payment.amount = 0
                            if payment.code == 'walle':
                                self.env['switch.payment.method.wizard']._update_wallet_reservation_safely(order)
            self.env['switch.payment.method.wizard']._trigger_so_update_service(order)
            self.env['switch.payment.method.wizard']._schedule_activity_to_update_delivery_partner(order)
            zero_payments = order.mataa_payment_ids.filtered(lambda p: p.amount <= 0)
            if zero_payments:
                zero_payments.unlink()

    offer_tag_ids = fields.Many2many("product.offer.tag",
                                     string="Offer Tags",
                                     compute="_compute_offer_tags",
                                     store=False,
                                     )

    @api.depends("order_line.product_id.offer_tag_ids")
    def _compute_offer_tags(self):
        for order in self:
            tags = order.order_line.mapped("product_id.offer_tag_ids")
            order.offer_tag_ids = tags

    refund_type = fields.Selection(
        [('replacement', 'استبدال'), ('refund', 'استرجاع')],
        string="نوع الطلب", required=True
    )
    refund_reason_ids = fields.Many2many(
        'sale.order.reason',
        string='السبب',
        copy=False,
        domain="[('reason_type', '=', 'refund')]"
    )
    refund_description = fields.Text(string='Refund Description', copy=False)

    refund_value_method = fields.Selection(
        [('wallet', 'محفظة'), ('cash', 'نقدا')],
        string=" القيمة ", required=True
    )

    ecommerce_status = fields.Selection([
        ('in_to_be_ordered', 'To Be Ordered'),
        ('in_waiting_for_confirmation', 'Waiting for confirmation'),
        ('in_preparing', 'Preparing'),
        ('in_picked_up', 'Picked up'),
        ('in_not_available', 'Not available'),
        ('in_partially_available', 'Partially available'),
        ('available_at_warehouse', 'Available at the warehouse'),
        ('out_picking', 'Picking'),
        ('out_packing', 'Packing'),
        ('out_ready', 'Ready'),
        ('out_handling', 'Handling'),
        ('out_shipping', 'Shipping'),
        ('out_partially_delivered', 'Partially Delivered'),
        ('out_delivered', 'Delivered'),
        ('out_returned', 'Returned'),
        ('canceled', 'Canceled')
    ], string='E-commerce Status', compute='_compute_ecommerce_status', store=True, readonly=True)

    mataa_order_create_date = fields.Datetime(
        string='Mataa Order Creation Date',
        default=lambda self: fields.Datetime.now(),
    )

    customer_phone = fields.Char('Phone', related='partner_id.phone')

    mata_order_state = fields.Selection([('wc-verifying', 'قيد التاكيد'),  # FROM WP TO ODOO
                                         ('wc-on-hold', 'قيد الانتظار'),  # FROM WP TO ODOO
                                         ('startpacking', 'قيد التجهيز'),  # S.O QUOTATION CONFIRM
                                         ('kindacompleted', 'جاري التغليف'),  # S.O "PICK" ORDER  IS "DONE"
                                         ('packingdone', 'تم التجهيز'),  # S.O IS IN "DELIVERY ORDER" SATAGE
                                         ('processing', 'قيد التوصيل'),
                                         # S.O IS IN "DELIVERY ORDER" STAGE AND CONFINED {LINE DELIVERY}
                                         ('shipping', 'قيد الشحن'),
                                         # S.O IS IN "DELIVERY ORDER" SATAGE AND CONFINED {CAMEX DELIVERY}
                                         ('completed', 'مكتمل'),  # WHEN DELIVERY COMPANY LEVELLED THE ORDER
                                         ('failed', 'فشل'),  # CANCEL S.O WHILE STILL IN  ( SALES ORDER) AND AFTER
                                         ('cancelled', 'ملغي')
                                         # CANCEL S.O WHILE STILL IN ( Quotation AND Quotation SENT )
                                         ], default=False, copy=False, tracking=True)

    mata_shipment_state = fields.Selection([('fully_delivered', 'Fully Delivered'),
                                            ('partially_delivered', 'Partially Delivered'),
                                            ('fully_returned', 'Fully Returned'),
                                            ('fully_refunded', 'Fully Refunded'),
                                            ('fully_replaced', 'Fully Replaced')
                                            ], default=False, copy=False, tracking=True)

    is_handled = fields.Boolean(default=False)

    mata_order_id = fields.Char(
        string='Mataa Order ID',
        readonly=True, tracking=True, copy=False,
        help='The Mataa Order ID linked to this sale order'
    )

    mataa_coupon_ids = fields.One2many(
        'mataa.sales.coupon',
        'sale_order_id',
        string='Mataa Coupons', copy=False,
        help='Mataa Coupons related to this order'
    )

    mataa_payment_ids = fields.One2many(
        'mataa.so.payment',
        'sale_order_id',
        string='Mataa Payments', copy=False,
        help='Mataa Payments related to this order'
    )

    reservation_entry_id = fields.Many2one(
        comodel_name='account.move',
        string="Reservation Entry", copy=False,
        readonly=True, tracking=True
    )

    shipment_bill_id = fields.Many2one(
        comodel_name='account.move',
        string="Shipment Bill", copy=False,
        readonly=True, tracking=True
    )

    refunded_order_id = fields.Many2one(
        comodel_name='sale.order',
        string="Origin/Refunded Order", copy=False,
        readonly=True, tracking=True
    )

    refund_ids = fields.One2many(
        'sale.order',
        'refunded_order_id',
        string='Refunds', copy=False, readonly=True,
        help='Refunds for this order'
    )
    is_refund_order = fields.Boolean(copy=False, tracking=True, readonly=True)
    is_replacement_order = fields.Boolean(compute='_compute_is_replacement_order')

    internal_note = fields.Text(
        'Internal Note', translate=True,
        help="Used as an internal Note for Mataa Team")

    mataa_customer_note = fields.Text(
        'Customer Note', translate=True,
        help="Used as an customer Note for Mataa order")

    show_reservation_button = fields.Boolean(compute='_compute_show_reservation_button')

    show_closing_button = fields.Boolean(compute='_compute_show_closing_button')
    show_refund_button = fields.Boolean(compute='_compute_show_refund_button')

    mataa_purchases_count = fields.Integer(compute='get_mataa_purchases')
    mataa_sales_count = fields.Integer(compute='compute_mataa_sales_count')
    mataa_active_sales_count = fields.Integer(compute='compute_mataa_active_sales_count')
    mataa_quotations_count = fields.Integer(compute='compute_mataa_quotations_count')
    mataa_bundles_count = fields.Integer(compute='compute_mataa_bundles_count')
    mataa_tickets_count = fields.Integer(compute='compute_mataa_tickets_count')
    mataa_refunds_count = fields.Integer(compute='compute_mataa_refunds_count')
    mataa_related_payment_count = fields.Integer(compute='compute_mataa_related_payment_count')

    mataa_tag_ids = fields.Many2many('so.tag', 'mataa_so_tag_rel', 'order_id_id', 'tag_id', string='SO Tags')
    customer_tag_ids = fields.Many2many('res.partner.category', string='Customer Tags',
                                        related="partner_id.category_id")

    mataa_bundle_id = fields.Many2one('so.bundle', string='SO Bundle', copy=False)

    active = fields.Boolean(default=True, tracking=True)

    compensation_reason_id = fields.Many2one(
        'compensation.reason',
        string='Compensation Reason',
        copy=False,
        tracking=True,
        help='Reason for the compensation'
    )

    compensation_description = fields.Text(
        string='Compensation Description',
        copy=False,
        tracking=True,
        help='Detailed description of the compensation'
    )

    compensation_amount = fields.Monetary(
        string='Compensation Amount',
        currency_field='currency_id',
        copy=False,
        tracking=True,
        help='Amount to be compensated to the customer wallet'
    )

    compensation_user_id = fields.Many2one(
        'res.users',
        string='Compensation User',
        copy=False,
        tracking=True,
        help='User who created the compensation'
    )

    compensation_date = fields.Datetime(
        string='Compensation Date',
        copy=False,
        tracking=True,
        help='Date when compensation was applied'
    )

    compensation_journal_entry_id = fields.Many2one(
        'account.move',
        string='Compensation Journal Entry',
        copy=False,
        readonly=True,
        tracking=True,
        help='Journal entry created for the compensation'
    )

    show_compensation_button = fields.Boolean(
        compute='_compute_show_compensation_button',
        help='Show compensation button based on compensation window and reason'
    )

    show_update_payment_button = fields.Boolean(
        compute='_compute_show_update_payment_button',
        help='Show update payment buttons during allowed window'
    )

    show_cod_to_wallet_button = fields.Boolean(compute='_compute_show_payment_buttons')
    show_wallet_to_cod_button = fields.Boolean(compute='_compute_show_payment_buttons')

    total_quantity = fields.Float(string="Total Quantity", compute="_compute_total_quantity", store=True)

    dms_delegate_commission = fields.Float(
        string="DMS Delegate Commission",
        readonly=True, copy=False, tracking=True,
        help="The commission amount for the DMS delegate, received from the settlement webhook."
    )

    inhouse_line_count = fields.Integer(
        string='Inhouse Product Count',
        compute='_compute_inhouse_line_count',
        store=True,
        readonly=True,
        help="Counts the number of order lines with products from the inhouse location."
    )

    inhouse_total_qty = fields.Float(
        string='Inhouse Product Quantity',
        compute='_compute_inhouse_total_qty',
        store=True,
        readonly=True,
        help="Calculates the total quantity of products from the inhouse location."
    )
    coupon_applied = fields.Boolean(default=False)
    coupon_type = fields.Selection([
        ('fixed_discount', 'Fixed Discount'),
        ('percentage_discount', 'Percentage Discount'),
    ])
    discount_amount = fields.Float()
    discount_percentage = fields.Float()

    is_shipping_offer = fields.Boolean(
        string="Is Shipping Offer",
        default=False,
        copy=False,
        help="Check if the order has a special shipping offer from external system."
    )

    actual_shipping_cost = fields.Monetary(
        string="Actual Shipping Cost",
        currency_field='currency_id',
        default=0.0,
        copy=False,
        help="The real shipping cost received from external system, used for vendor bill generation."
    )

    shipping_offer_name = fields.Char(
        string="Shipping Offer Name",
        copy=False,
        help="Name of the shipping offer"
    )

    from_shipping_to_inwarehouse_duration = fields.Char(
        string="Time from shipping request to in warehouse",
        compute='_compute_dms_status_changes_time',
        readonly=True
    )

    from_inwarehouse_to_delivered_duration = fields.Char(
        string="Time from in warehouse to delivered",
        compute='_compute_dms_status_changes_time',
        readonly=True
    )

    from_on_delivery_to_delivered_duration = fields.Char(
        string="Time from on delivery to delivered",
        compute='_compute_dms_status_changes_time',
        readonly=True
    )

    @api.depends('dms_shipment_status')
    def _compute_dms_status_changes_time(self):
        for order in self:
            order.from_shipping_to_inwarehouse_duration = "NOT done yet"
            order.from_inwarehouse_to_delivered_duration = "NOT done yet"
            order.from_on_delivery_to_delivered_duration = "NOT done yet"
            if not order.dms_shipment_status:
                continue

            shipment_changes = self.env['mail.tracking.value'].sudo().search([
                ('mail_message_id.model', '=', 'sale.order'),
                ('mail_message_id.res_id', '=', order.id),
                ('field_id.name', '=', 'dms_shipment_status'),
            ], order='create_date asc')

            if not shipment_changes:
                continue

            previous = self.env['mail.tracking.value'].sudo().search([
                ('mail_message_id.model', '=', 'sale.order'),
                ('mail_message_id.res_id', '=', order.id),
                ('field_id.name', '=', 'mata_order_state'),
                ('old_value_char', '=', 'جاري التغليف'),
                ('new_value_char', '=', 'تم التجهيز')
            ])
            if len(previous) > 1:
                continue
            for current in shipment_changes:
                if not previous:
                    previous = current
                    continue

                time_delta = current.create_date - previous.create_date

                if current.old_value_char == 'قيد الانتظار' and current.new_value_char == 'في المخزن':
                    order.from_shipping_to_inwarehouse_duration = str(time_delta).split('.')[0]

                if current.old_value_char == 'في المخزن' and current.new_value_char == 'قيد التوصيل':
                    order.from_inwarehouse_to_delivered_duration = str(time_delta).split('.')[0]

                if current.old_value_char == 'قيد التوصيل' and current.new_value_char == 'تم التسليم':
                    order.from_on_delivery_to_delivered_duration = str(time_delta).split('.')[0]

                previous = current

    def action_open_external_system(self):
        external_url = self.env['ir.config_parameter'].sudo().get_param('mataa_order_management.external_sale_url')
        return {
            'type': 'ir.actions.act_url',
            'url': external_url,
            'target': 'new',
        }

    @api.depends('order_line.product_id', 'order_line.product_qty')
    def _compute_total_quantity(self):
        for order in self:
            order.total_quantity = sum(
                line.product_qty for line in order.order_line
                if line.product_id and line.product_id.detailed_type != 'service'
            )

    related_account_payment_ids = fields.Many2many(
        'account.payment',
        'sale_order_account_payment_rel',
        'sale_order_id',
        'payment_id'
    )

    is_suspended = fields.Boolean(string="Suspended" ,default=False, tracking=True)
    
    def action_toggle_suspended(self):
        for order in self:
            order.is_suspended = not order.is_suspended
    
    def action_open_sale_suspension_wizard(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "sale.suspension.wizard",
            "view_mode": "form",
            "target": "new",
            "view_id": self.env.ref("mataa_order_management.view_sale_suspension_wizard_form").id,
            "context": {
                "default_sale_order_id": self.id,
            },
        }

    def add_payment(self, payment_id):
        """Add a payment record to the sale order's payment_ids M2M field."""
        payment = self.env['account.payment'].browse(payment_id)
        if not payment.exists():
            raise ValueError(f"Payment ID {payment_id} does not exist.")
        for order in self:
            order.related_account_payment_ids = [(4, payment.id)]

    def toggle_active(self):
        if self.filtered(lambda po: po.state != "cancel" and po.active):
            raise UserError(_("Only 'Canceled' orders can be archived"))
        return super().toggle_active()

    def get_mataa_purchases(self):
        for record in self:
            purchases = self.env['purchase.order'].search([('sale_order_id', '=', record.id)])
            record.mataa_purchases_count = len(purchases)

    def compute_mataa_sales_count(self):
        for record in self:
            orders = self.env['sale.order'].search([
                ('id', '!=', record._origin.id),
                ('partner_id', '=', record.partner_id.id)])
            record.mataa_sales_count = len(orders)

    @api.depends('ecommerce_status', 'partner_id')
    def compute_mataa_active_sales_count(self):
        for record in self:
            orders = self.env['sale.order'].search([
                ('id', '!=', record._origin.id),
                ('partner_id', '=', record.partner_id.id),
                ('state', '=', 'sale'),
                ('ecommerce_status', 'not in',
                 ['out_shipping', 'out_partially_delivered', 'out_delivered', 'out_returned', 'canceled'])])
            record.mataa_active_sales_count = len(orders)

    def compute_mataa_quotations_count(self):
        for record in self:
            quotations = self.env['sale.order'].search([
                ('id', '!=', record._origin.id),
                ('partner_id', '=', record.partner_id.id),
                ('state', 'in', ['draft', 'sent'])])
            record.mataa_quotations_count = len(quotations)

    def compute_mataa_bundles_count(self):
        for record in self:
            so_ids = self.mataa_bundle_id.mataa_bundled_so_ids - self
            record.mataa_bundles_count = len(so_ids)

    def compute_mataa_tickets_count(self):
        for record in self:
            tickets = self.env['helpdesk.ticket'].search([('mataa_so_id', '=', record.id)])
            record.mataa_tickets_count = len(tickets)

    def compute_mataa_refunds_count(self):
        for record in self:
            record.mataa_refunds_count = len(record.refund_ids)

    def compute_mataa_related_payment_count(self):
        for record in self:
            record.mataa_related_payment_count = len(record.related_account_payment_ids)

    @api.depends('order_line.status', 'state')
    def _compute_ecommerce_status(self):
        priority = [
            'in_to_be_ordered',
            'in_waiting_for_confirmation',
            'in_preparing',
            'in_picked_up',
            'in_not_available',
            'in_partially_available',
            'available_at_warehouse',
            'out_picking',
            'out_packing',
            'out_ready',
            'out_handling',
            'out_shipping',
            'out_partially_delivered',
            'out_delivered',
            'out_returned',
            'canceled'
        ]

        for order in self:
            if order.state == "cancel":
                order.ecommerce_status = "canceled"
            else:
                statuses = order.mapped('order_line.status')
                if statuses:
                    for status in priority:
                        if status in statuses:
                            order.ecommerce_status = status
                            break
                else:
                    order.ecommerce_status = False

    @api.depends('reservation_entry_id', 'mataa_payment_ids')
    def _compute_show_reservation_button(self):
        for order in self:
            order.show_reservation_button = False
            if order.get_e_payment_amount() > 0 and not order.reservation_entry_id and order.amount_total > 0:
                order.show_reservation_button = True

    @api.depends('picking_ids', 'is_handled', 'mata_shipment_state')
    def _compute_show_closing_button(self):
        # When the order is ready for closing?
        for order in self:
            show_button = True
            # Check for an outgoing picking that is not done
            outgoing_picking = order.picking_ids.filtered(lambda picking: picking.picking_type_code == "outgoing")
            if outgoing_picking and outgoing_picking[0].state != "done":
                show_button = False

            # Check if the order is handled or shipment state is not set
            if order.is_handled or not order.mata_shipment_state:
                show_button = False

            # Assign the result
            order.show_closing_button = show_button

    @api.depends('picking_ids', 'is_handled', 'mata_shipment_state')
    def _compute_show_refund_button(self):
        # When the order is ready for refund?
        for order in self:
            order.show_refund_button = not order.is_refund_order

    @api.depends('picking_ids', 'picking_ids.date_done')
    def _compute_show_compensation_button(self):
        for order in self:
            order.show_compensation_button = False

            if not order.compensation_reason_id:
                compensation_window = self.env['ir.config_parameter'].sudo().get_param(
                    'mataa_order_management.compensation_window_days', '30'
                )
                try:
                    compensation_window = int(compensation_window)
                except ValueError:
                    compensation_window = 30

                latest_delivery = order.picking_ids.filtered(
                    lambda p: p.picking_type_code == 'outgoing' and p.state == 'done'
                ).sorted('date_done', reverse=True)

                if latest_delivery:
                    delivery_date = latest_delivery[0].date_done
                    days_since_delivery = (fields.Datetime.now() - delivery_date).days

                    if days_since_delivery <= compensation_window:
                        order.show_compensation_button = True

    @api.depends('state', 'is_handled', 'mata_shipment_state')
    def _compute_show_update_payment_button(self):
        for order in self:
            order.show_update_payment_button = order.state in ('draft', 'sent', 'sale') and not order.is_handled

    @api.depends('show_update_payment_button', 'mataa_payment_ids', 'amount_total')
    def _compute_show_payment_buttons(self):
        for order in self:
            order.show_cod_to_wallet_button = False
            order.show_wallet_to_cod_button = False

            if not order.show_update_payment_button:
                continue

            total_e_payments = order.get_total_e_payments()
            total_cod_payments = order.get_shipment_price()

            if total_cod_payments > 0:
                order.show_cod_to_wallet_button = True

            if total_e_payments > 0:
                order.show_wallet_to_cod_button = True

    @api.depends('order_line', 'order_line.product_uom_qty')
    def _compute_is_replacement_order(self):
        for order in self:
            lines = order.order_line.filtered(lambda line: not line.is_delivery and line.product_uom_qty > 0)
            if order.is_refund_order and lines:
                order.is_replacement_order = True
            else:
                order.is_replacement_order = False

    @api.depends('mata_order_state')
    def _compute_time_taken(self):
        for order in self:
            trackings = self.env['mail.tracking.value'].sudo().search([
                ('mail_message_id.model', '=', 'sale.order'),
                ('mail_message_id.res_id', '=', order.id),
                ('field_id.name', '=', 'mata_order_state'),
            ], order='create_date asc')
            if not trackings:
                order.time_taken = "00:00"
            else:
                start_dt = trackings[0].create_date
                end_dt = trackings[-1].create_date
                if not start_dt or not end_dt:
                    order.time_taken = "00:00"
                    continue
                delta = end_dt - start_dt
                total_seconds = int(max(delta.total_seconds(), 0))
                hours = total_seconds // 3600
                minutes = (total_seconds % 3600) // 60
                order.time_taken = f"{hours:02d}:{minutes:02d}"

    @api.constrains('mata_order_id')
    def _check_unique_mata_order_id(self):
        for record in self:
            if record.mata_order_id:
                existing_order = self.search([('mata_order_id', '=', record.mata_order_id), ('id', '!=', record.id)])
                if existing_order:
                    raise UserError(
                        f"The following internal reference: {record.mata_order_id} was found in other orders. \n"
                        "Note that order internal references should not repeat."
                    )

    @api.constrains('mataa_bundle_id')
    def _check_unique_customer(self):
        self.ensure_one()
        partner_ids = self.mataa_bundle_id.mataa_bundled_so_ids.mapped('partner_id')
        if len(partner_ids) > 1:
            raise UserError('Cannot bundle orders for multi customers')

    def _get_invoiceable_lines(self, final=False):
        invoiceable_line_ids = super(SaleOrder, self)._get_invoiceable_lines(final)

        precision = self.env['decimal.precision'].precision_get('Product Unit of Measure')

        mata_invoiceable_line_ids = invoiceable_line_ids
        if self._context.get('use_mataa_qty', False):
            for invoiceable_line_id in invoiceable_line_ids:
                if invoiceable_line_id.display_type not in ['line_note', 'line_section'] and float_is_zero(
                        invoiceable_line_id.mataa_qty_to_invoice, precision_digits=precision):
                    mata_invoiceable_line_ids = mata_invoiceable_line_ids - invoiceable_line_id
        return mata_invoiceable_line_ids

    def get_shipment_price(self):
        self.ensure_one()

        total_e_payments = self.get_total_e_payments()

        total_cod_payments = abs(self.amount_total) - total_e_payments
        if not self.is_refund_order and total_cod_payments < 0:
            total_cod_payments = 0

        return total_cod_payments

    def get_total_e_payments(self):
        self.ensure_one()

        e_journal_codes = [self.company_id.wallet_reservation_journal_id.code]
        e_journal_codes += self.env['account.journal'].sudo().search([('e_payment_journal', '=', True)]).mapped('code')
        total_e_payments = sum(p.amount for p in self.mataa_payment_ids if p.code in e_journal_codes)

        return total_e_payments

    def get_pick_info(self):
        self.ensure_one()

        picking_ids = self.picking_ids
        pack_picking_ids = picking_ids.filtered(lambda p: p.picking_type_id.sequence_code == "PACK")
        if picking_ids:
            picking_id = pack_picking_ids and pack_picking_ids[0] or picking_ids[0]
            return {
                "pick_name": picking_id.name,
                "pick_tracking": picking_id.carrier_tracking_ref,
            }
        return {
            "pick_name": "null",
            "pick_tracking": "null",
        }

    def get_shipping_price(self):
        self.ensure_one()
        amount = sum(self.order_line.filtered(lambda line: line.is_delivery).mapped('price_subtotal'))
        return amount

    def get_order_note(self):
        self.ensure_one()
        note = self.mataa_customer_note if self.mataa_customer_note else ''
        if self.is_replacement_order:
            note += "\n هذا طلب تبديل، يحب استلام المنتجات التالية من العميل:"
            lines = self.order_line.filtered(lambda line: not line.is_delivery and line.product_uom_qty < 0)
            for line in lines:
                note += f"\n- المنتج:"
                note += f"\n    * اسم المنتج: {line.product_id.name}"
                note += f"\n    * الكمية: {abs(line.product_uom_qty)}"
                note += f"\n    * SKU: {line.product_id.default_code}"
        return note

    def update_mataa_status(self, mataa_state=None):
        # Todo: clean this code
        for order_id in self:
            current_state = order_id.mata_order_state

            # if mataa_state == "processing":
            #     order_id.mata_order_state = mataa_state
            #     SaleOrderSyncService.update_status(order_id.id, order_id.mata_order_state)

            if mataa_state:
                order_id.mata_order_state = mataa_state
            elif order_id.picking_ids:
                out_id = order_id.picking_ids.filtered(lambda picking: picking.picking_type_code == "outgoing")
                pick_id = order_id.picking_ids.filtered(lambda picking: "PICK" in picking.name)
                if out_id:
                    out_id = out_id[0]
                    if out_id.state == "assigned":
                        order_id.mata_order_state = "packingdone"

                    elif pick_id and pick_id[0].state == "done" and out_id.state != "done":
                        order_id.mata_order_state = "kindacompleted"

                    elif pick_id and pick_id[0].state == "failed":
                        order_id.mata_order_state = "kindacompleted"

                    elif order_id.state == "sale" and out_id.state != "done":
                        order_id.mata_order_state = "startpacking"

            elif order_id.state == "sale" and not order_id.carrier_id:
                order_id.mata_order_state = "startpacking"

            if current_state != order_id.mata_order_state or mataa_state:
                try:
                    SaleOrderSyncService.update_status(order_id.mata_order_id, order_id.mata_order_state)
                except Exception as e:
                    _logger.info(f"{e}")

    def update_order_stage(self):
        for order_id in self:
            # Get all completed outgoing pickings
            outgoing_pickings = order_id.picking_ids.filtered(
                lambda p: p.state == 'done' and p.picking_type_code == "outgoing"
            )

            # Check if all outgoing pickings have completed returns
            fully_returned = True

            if not outgoing_pickings:
                fully_returned = False
            else:
                for picking in outgoing_pickings:
                    if not picking.return_ids or any(return_id.state != "done" for return_id in picking.return_ids):
                        fully_returned = False
                        break

                    # calculate the returned quantities and compare them with the quantities that were delivered
                    returned_quantities = {}
                    for return_picking in picking.return_ids.filtered(lambda p: p.state == 'done'):
                        for move in return_picking.move_ids:
                            returned_quantities[move.product_id.id] = returned_quantities.get(move.product_id.id,
                                                                                              0.0) + move.quantity

                    for move in picking.move_ids:
                        product_id = move.product_id.id
                        qty_done = move.quantity
                        returned_qty = returned_quantities.get(product_id, 0.0)
                        if returned_qty < qty_done:
                            fully_returned = False
                            break
                    if not fully_returned:
                        break

            # Cancel order if fully returned
            if fully_returned:
                order_id._action_cancel()

    def close_mataa_order(self, shipment_status):
        res = super(SaleOrder, self).close_mataa_order(shipment_status)
        self.order_line.update_line_status()
        if shipment_status == "fully_returned":
            self.update_mataa_status("failed")
        else:
            self.update_mataa_status("completed")
        # self.create_order_closing_ticket()
        return res

    def close_fully_delivered_order(self):
        self.ensure_one()
        self.mata_shipment_state = "fully_delivered"
        # Order finalization will be manual for now
        # self.finalize_mataa_order()

    def close_partially_delivered_order(self):
        self.ensure_one()
        self.mata_shipment_state = "partially_delivered"
        self.update_mataa_status("completed")
        self.create_order_closing_activity()

    def close_fully_returned_order(self):
        for order_id in self.filtered(lambda order: not order.mata_shipment_state):

            picking_ids = order_id.picking_ids.filtered(lambda p:
                                                        p.state == 'done' and
                                                        p.picking_type_code == "outgoing" and
                                                        not p.return_ids)

            for picking_id in picking_ids:
                return_wiz = self.env['stock.return.picking'].sudo().with_context(
                    active_model="stock.picking", active_id=picking_id.id, active_ids=picking_id.ids).create({
                    "picking_id": picking_id.id
                })
                return_wiz._compute_moves_locations()
                return_wiz.create_returns()

            order_id.mata_shipment_state = "fully_returned"
            # Order finalization will be manual for now
            # order_id.finalize_mataa_order()

        # In case manually closing
        # self.order_line.update_line_status()
        # self.update_mataa_status("completed")
        # self.create_order_closing_ticket()

    def finalize_mataa_order(self):
        # Create invoice, Payment, Create the bill
        for order_id in self.filtered(lambda order: not order.is_handled):

            order_id.is_handled = True

            carrier_id = order_id.carrier_id
            trigger_code_setting = order_id.company_id.card_on_delivery_trigger_code
            destination_journal = order_id.company_id.card_on_delivery_journal_id

            if trigger_code_setting and destination_journal and \
                    order_id.mataa_payment_ids.filtered(lambda p: p.code == trigger_code_setting):

                cod_journal_id = destination_journal
            else:

                cod_journal_id = carrier_id.cod_journal_id
            carrier_partner_id = carrier_id.carrier_partner_id

            delivery_lines = order_id.order_line.filtered('is_delivery')
            if delivery_lines and delivery_lines[0].mataa_original_price > 0:
                delivery_cost = delivery_lines[0].mataa_original_price
            else:
                delivery_cost = sum(delivery_lines.mapped('price_total'))
            dms_commission = order_id.dms_delegate_commission

            if order_id.is_shipping_offer and order_id.actual_shipping_cost > 0:
                bill_amount_to_pay = order_id.actual_shipping_cost
            else:
                bill_amount_to_pay = delivery_cost

            if carrier_id.delivery_type == 'dms' and dms_commission > 0:
                bill_amount_to_pay = dms_commission

            use_mataa_qty = True
            if order_id.is_refund_order:
                use_mataa_qty = False
            if order_id.with_context(use_mataa_qty=use_mataa_qty)._get_invoiceable_lines(final=True):

                invoice_id = order_id.with_context(use_mataa_qty=use_mataa_qty)._create_invoices(final=True)

                if len(invoice_id) != 1:
                    raise UserError(_("For each order only one invoice can be issued"))

                invoice_id.action_post()

                # if order_id.is_refund_order:
                #     original_order_id = order_id.refunded_order_id
                #     # send payment
                #     refund_orders_journal_id = order_id.company_id.refund_orders_journal_id
                #     if not refund_orders_journal_id:
                #         raise UserError(_("Refund orders journal is missing"))
                #     payment_register = self.env['account.payment.register'].with_context(
                #         active_model='account.move.line',
                #         active_ids=invoice_id.line_ids.ids).create({
                #         'journal_id': refund_orders_journal_id.id,
                #     })
                #     payment_register._compute_amount()
                #     refund_new_payment_id = payment_register._create_payments()
                #
                #     # Receive Payment
                #     if refund_new_payment_id:
                #         order_id.add_payment(refund_new_payment_id.id)
                #
                #         # Receive Payment
                #         # Create a customer payment
                #         payment_id = self.env['account.payment'].create({
                #             'partner_id': order_id.partner_id.id,
                #             'journal_id': refund_orders_journal_id.id,
                #             'amount': refund_new_payment_id.amount,
                #             'ref': "ايداع في المحفظة مقابل ارجاع رقم %s" % invoice_id.name,
                #             'payment_type': 'inbound',
                #             'partner_type': 'customer',
                #         })
                #         payment_id.action_post()
                #         order_id.add_payment(payment_id.id)

                if order_id.is_refund_order:
                    # original_order_id = order_id.refunded_order_id

                    # refund_delivery_cost = sum(order_id.order_line.filtered('is_delivery').mapped('price_total'))
                    #
                    # original_delivery_cost = sum(original_order_id.order_line.filtered('is_delivery').mapped('price_total'))
                    #
                    # refund_amount_total = abs(sum(order_id.order_line.filtered(lambda l: not l.is_delivery).mapped('price_total'))) + refund_delivery_cost
                    #
                    # original_amount_total = original_order_id.amount_total - original_delivery_cost
                    #
                    # refund_difference = refund_amount_total - original_amount_total

                    original_amount_total = order_id.amount_total
                    refund_difference = original_amount_total

                    mataa_total_payment = sum(order_id.mataa_payment_ids.mapped('amount'))
                    mataa_e_payment = order_id.get_e_payment_amount()
                    mataa_cash_payment = mataa_total_payment - mataa_e_payment

                    # Case 1: No difference in amount
                    if refund_difference == 0:
                        pass
                        # send payment
                        # refund_journal = order_id.company_id.refund_orders_journal_id
                        # if not refund_journal:
                        #     raise UserError(_("Refund orders journal is missing."))
                        #
                        # payment_register = self.env['account.payment.register'].with_context(
                        #     active_model='account.move.line',
                        #     active_ids=invoice_id.line_ids.ids
                        # ).create({
                        #     'journal_id': refund_journal.id,
                        # })
                        # payment_register._compute_amount()
                        # refund_payment = payment_register._create_payments()
                        #
                        # # Receive Payment
                        # if refund_payment:
                        #     order_id.add_payment(refund_payment.id)
                        #
                        #     wallet_payment = self.env['account.payment'].create({
                        #         'partner_id': order_id.partner_id.id,
                        #         'journal_id': refund_journal.id,
                        #         'amount': refund_payment.amount,
                        #         'ref': "ايداع في المحفظة مقابل ارجاع رقم %s" % invoice_id.name,
                        #         'payment_type': 'inbound',
                        #         'partner_type': 'customer',
                        #     })
                        #     wallet_payment.action_post()
                        #     order_id.add_payment(wallet_payment.id)

                    # Case 2: New order is more expensive → Customer must pay the difference
                    elif refund_difference > 0:

                        # Cash payment
                        if mataa_cash_payment > 0:
                            payment_register = self.env['account.payment.register'].with_context(
                                active_model='account.move.line',
                                default_sale_order_id=order_id.id,
                                active_ids=invoice_id.line_ids.ids).create({
                                'amount': mataa_cash_payment,
                                'journal_id': cod_journal_id.id,
                            })
                            new_cod_payment_id = payment_register._create_payments()
                            if new_cod_payment_id:
                                order_id.add_payment(new_cod_payment_id.id)
                        # ePayments
                        if mataa_e_payment > 0:
                            invoice_id.invalidate_recordset(['invoice_outstanding_credits_debits_widget'])
                            widget_vals = invoice_id.invoice_outstanding_credits_debits_widget
                            if widget_vals:
                                outstanding_list = widget_vals.get('content', [])
                                for outstanding in outstanding_list:
                                    aml_int_id = outstanding.get('id', False)
                                    payment_int_id = outstanding.get('account_payment_id', False)
                                    payment_id = self.env['account.payment'].browse(payment_int_id)
                                    if payment_id.journal_id.e_payment_journal:
                                        if payment_id.mataa_payment_id.id in order_id.mataa_payment_ids.ids:
                                            invoice_id.js_assign_outstanding_line(aml_int_id)

                    # Case 3: New order is cheaper → The customer is entitled to a refund
                    elif refund_difference < 0:

                        # Cash payment
                        if mataa_cash_payment > 0:
                            raise UserError(_("Cash refunds are currently disabled."))
                            payment_register = self.env['account.payment.register'].with_context(
                                active_model='account.move.line',
                                default_sale_order_id=order_id.id,
                                active_ids=invoice_id.line_ids.ids).create({
                                'amount': mataa_cash_payment,
                                'journal_id': cod_journal_id.id,
                            })
                            new_cod_payment_id = payment_register._create_payments()
                            if new_cod_payment_id:
                                order_id.add_payment(new_cod_payment_id.id)
                        # ePayments
                        if mataa_e_payment > 0:
                            # send payment
                            refund_journal = order_id.company_id.refund_orders_journal_id
                            if not refund_journal:
                                raise UserError(_("Refund orders journal is missing."))

                            payment_register = self.env['account.payment.register'].with_context(
                                active_model='account.move.line',
                                default_sale_order_id=order_id.id,
                                active_ids=invoice_id.line_ids.ids
                            ).create({
                                'journal_id': refund_journal.id,
                            })
                            payment_register._compute_amount()
                            refund_payment = payment_register._create_payments()

                            # Receive Payment
                            if refund_payment:
                                order_id.add_payment(refund_payment.id)

                                wallet_payment = self.env['account.payment'].create({
                                    'partner_id': order_id.partner_id.id,
                                    'journal_id': refund_journal.id,
                                    'amount': refund_payment.amount,
                                    'ref': "ايداع في المحفظة مقابل ارجاع رقم %s" % invoice_id.name,
                                    'payment_type': 'inbound',
                                    'partner_type': 'customer',
                                })
                                wallet_payment.action_post()
                                order_id.add_payment(wallet_payment.id)

                else:
                    cod_amount = order_id.get_shipment_price()
                    if cod_amount > 0 and invoice_id.amount_total == order_id.amount_total:
                        # Cash payment
                        payment_register = self.env['account.payment.register'].with_context(
                            active_model='account.move.line',
                            default_sale_order_id=order_id.id,
                            active_ids=invoice_id.line_ids.ids).create({
                            'amount': cod_amount,
                            'journal_id': cod_journal_id.id,
                        })
                        new_payment_id = payment_register._create_payments()
                        if new_payment_id:
                            order_id.add_payment(new_payment_id.id)

                    invoice_id.invalidate_recordset(['invoice_outstanding_credits_debits_widget'])
                    widget_vals = invoice_id.invoice_outstanding_credits_debits_widget
                    if widget_vals:
                        # ePayments
                        outstanding_list = widget_vals.get('content', [])
                        for outstanding in outstanding_list:
                            aml_int_id = outstanding.get('id', False)
                            payment_int_id = outstanding.get('account_payment_id', False)
                            payment_id = self.env['account.payment'].browse(payment_int_id)
                            if payment_id.journal_id.e_payment_journal:
                                if payment_id.mataa_payment_id.id in order_id.mataa_payment_ids.ids:
                                    invoice_id.js_assign_outstanding_line(aml_int_id)

                        # Wallet payment
                        for outstanding in outstanding_list:
                            aml_int_id = outstanding.get('id', False)
                            payment_int_id = outstanding.get('account_payment_id', False)
                            payment_id = self.env['account.payment'].browse(payment_int_id)
                            if order_id.company_id.wallet_reservation_journal_id.code in order_id.mataa_payment_ids.mapped(
                                    'code'):
                                invoice_id.js_assign_outstanding_line(aml_int_id)
                                if payment_id:
                                    order_id.add_payment(payment_id.id)

                    if invoice_id.amount_total != order_id.amount_total and invoice_id.amount_residual > 0:
                        # Cash payment
                        payment_register = self.env['account.payment.register'].with_context(
                            active_model='account.move.line',
                            default_sale_order_id=order_id.id,
                            active_ids=invoice_id.line_ids.ids).create({
                            'journal_id': cod_journal_id.id,
                        })
                        payment_register._compute_amount()
                        cash_new_payment_id = payment_register._create_payments()
                        if cash_new_payment_id:
                            order_id.add_payment(cash_new_payment_id.id)

            order_id.clear_wallet_reservation()

            # Create the shipment bill
            if delivery_lines and carrier_partner_id and bill_amount_to_pay > 0:
                # Create the journal entry
                ref = _('فاتورة تكلفة الشحن لطلب مبيعات رقم %s') % order_id.name,
                bill_vals = {
                    'partner_id': carrier_partner_id.id,
                    'ref': ref,
                    'move_type': 'in_invoice',
                    'invoice_date': fields.Date.today(),
                    'date': fields.Date.today(),
                    'invoice_line_ids': [
                        (0, 0, {
                            'product_id': delivery_lines[0].product_id.id,
                            'quantity': 1,
                            'price_unit': round(bill_amount_to_pay, 2),
                            'tax_ids': False
                        })
                    ]
                }

                commission_amount = 0.0
                # Check if the delivery method and its fee product are properly configured
                fee_product = carrier_id.transfer_fee_product_id
                if fee_product:
                    # Find the correct fee from the vendor pricelist based on the SO total
                    order_total = order_id.amount_total
                    supplier_info = self.env['product.supplierinfo'].search([
                        ('product_tmpl_id', '=', fee_product.product_tmpl_id.id),
                        ('partner_id', '=', carrier_id.carrier_partner_id.id),
                        ('min_qty', '<=', order_total)
                    ], order='min_qty desc', limit=1)

                    # If a valid fee is found, add it as a new line on the bill
                    if supplier_info and supplier_info.price > 0:
                        commission_amount = round(supplier_info.price, 2)
                        bill_vals['invoice_line_ids'].append((0, 0, {
                            'product_id': fee_product.id,
                            'name': f"{fee_product.name} (Order: {order_id.name})",
                            'quantity': 1,
                            'price_unit': round(supplier_info.price, 2),
                            'tax_ids': False
                        }))

                # Create and post the shipment bill
                bill = self.env['account.move'].with_context({'default_move_type': 'in_invoice'}).sudo().create(
                    bill_vals)
                bill.action_post()
                order_id.shipment_bill_id = bill

                carrier_payment_journal = carrier_id.cod_journal_id

                if not carrier_payment_journal:
                    carrier_payment_journal = cod_journal_id

                payment_register = self.env['account.payment.register'].with_context(
                    active_model='account.move.line',
                    default_sale_order_id=order_id.id,
                    active_ids=bill.line_ids.ids).create({'amount': bill_amount_to_pay,
                                                           'journal_id': carrier_payment_journal.id})
                payment_register._create_payments()

                if commission_amount > 0:
                    comm_payment_register = self.env['account.payment.register'].with_context(
                        active_model='account.move.line',
                        default_sale_order_id=order_id.id,
                        active_ids=bill.line_ids.ids).create({
                        'amount': commission_amount,
                        'journal_id': carrier_payment_journal.id,
                        'communication': f" عمولة التوصيل للطلب {order_id.name} "
                    })
                    comm_payment_register._create_payments()

            # Fill the mata_shipment_state
            if not order_id.mata_shipment_state:
                if order_id.is_replacement_order:
                    order_id.mata_shipment_state = "fully_replaced"
                elif order_id.is_refund_order:
                    order_id.mata_shipment_state = "fully_refunded"
                else:
                    order_id.mata_shipment_state = "fully_delivered"

    def refund_mataa_order(self):
        self.ensure_one()

        # Check if the reasons were sent from the wizard
        if 'refund_reasons' in self.env.context:
            reason_data = self.env.context.get('refund_reasons', {})
            # This is the mapping {original_line_id: reason_id} we built in the wizard
            line_reasons = reason_data.get('line_reasons', {})

            order_lines = []
            # Filter: Must be delivered, must NOT be a delivery fee line, must NOT be a UI section/note
            eligible_lines = self.order_line.filtered(
                lambda l: l.mataa_qty_delivered > 0 and not l.is_delivery and not l.display_type
            )

            for line in eligible_lines:
                # Get the reason assigned to this specific line from the wizard
                reason_id = line_reasons.get(line.id)
                if not reason_id:
                    continue

                order_lines.append((0, 0, {
                    'product_id': line.product_id.id,
                    'product_uom_qty': line.mataa_qty_delivered * -1,
                    'price_unit': line.price_unit,
                    # Writing the reason directly to the line model
                    'refund_reason_id': reason_id, 
                }))

            # Create the refund order with header data and the new lines
            refund_id = self.with_context(skip_auto_confirm=True).create({
                "name": self.env['ir.sequence'].next_by_code('refund.order'),
                "refunded_order_id": self.id,
                "is_refund_order": True,
                "partner_id": self.partner_id.id,
                "mata_billing_phone": self.mata_billing_phone,
                "mata_shipping_phone": self.mata_shipping_phone,
                "mataa_city_id": self.mataa_city_id.id,
                "internal_note": self.internal_note,
                "mataa_customer_note": f"مرتجع لطلب رقم: {self.name}",
                # Header fields from wizard
                "refund_type": reason_data.get('refund_type'),
                "refund_value_method": reason_data.get('refund_value_method'),
                "refund_description": reason_data.get('refund_description'),
                "order_line": order_lines,
            })

            # Logic for delivery lines (if needed on the refund)
            delivery_line_ids = self.order_line.filtered(lambda l: l.is_delivery)
            if self.carrier_id and delivery_line_ids:
                line_id = delivery_line_ids[0]
                refund_id.add_delivery_method(self.carrier_id.id, line_id.price_unit)

            return {
                'name': 'Refund Order',
                'type': 'ir.actions.act_window',
                'res_model': 'sale.order',
                'res_id': refund_id.id,
                'view_mode': 'form',
                'target': 'current',
            }

        else:
            # Scenario 1: First click - Open the wizard
            return {
                'name': 'Add Refund Reason',
                'type': 'ir.actions.act_window',
                'res_model': 'sale.order.refund.reason.wizard',
                'view_mode': 'form',
                'target': 'new',
            }

    def action_confirm(self):
        self.order_line._cancel_draft_stock_move()

        refunds = self.filtered(lambda o: o.is_refund_order)
        refund_lines = refunds.mapped('order_line').filtered(lambda l: not l.is_delivery and l.product_uom_qty < 0)
        company_id = self and self[0].company_id or self.env.company
        refund_lines.write({'route_id': company_id.mataa_refund_route_id.id})

        for order in self:
            if order.show_reservation_button:
                raise UserError("You should make the wallet reservation before confirming this order.")

        # Extracted Line Logic (Inhouse check + RFQ creation)
        self.order_line.confirm_line()

        # Call the Super method to confirm
        res = super(SaleOrder, self).action_confirm()

        for order in self:
            order.order_line.update_line_status()
            order.update_mataa_status()

            if order.is_refund_order and not order.is_replacement_order:
                in_picking_id = order.picking_ids.filtered(lambda p: p.picking_type_id.sequence_code == "IN")
                carrier_id = in_picking_id.carrier_id
                if not carrier_id:
                    raise UserError(_('Please assign a Carrier to this transfer.'))
                if hasattr(carrier_id, '%s_send_shipping' % carrier_id.delivery_type):
                    getattr(carrier_id.with_context(is_refund=True), '%s_send_shipping' % carrier_id.delivery_type)(
                        in_picking_id)
                else:
                    raise UserError(_('Carrier API not available.'))
        return res


    def write(self, vals):
        res = super(SaleOrder, self).write(vals)

        if 'mataa_customer_note' in vals:
            self._apply_note_tag_rules()


        if 'dms_shipment_status' in vals:
            return res

        if self.env.context.get('skip_dms_shipment_update'):
            return res

        self.flush_recordset()

        for order in self:
            done_pack = self.env['stock.picking'].search([
                ('mataa_sale_order_id', '=', order.id),
                ('picking_type_id', '=', 4),
                ('state', '=', 'done'),
                ('carrier_id.delivery_type', '=', 'dms'),
                ('carrier_tracking_ref', '!=', False)
            ])
            for done in done_pack:
                done_pack.carrier_id.sudo().dms_update_shipment(done)

        return res

    def _action_cancel(self):
        for order in self:
            for line in order.order_line:
                line.mataa_order_line_process(line.product_uom_qty * -1)


            states_to_be_cancelled = ['wc-on-hold', 'wc-verifying', 'startpacking', 'kindacompleted', 'packingdone']
            states_to_be_failed = ['shipping', 'processing']
            if order.mata_order_state in states_to_be_cancelled:
                order.update_mataa_status("cancelled")
            elif order.mata_order_state in states_to_be_failed:
                order.update_mataa_status("failed")
            else:
                if order.state == 'sale':
                    order.update_mataa_status("failed")
                else:
                    order.update_mataa_status("cancelled")
            order.clear_wallet_reservation()

            order.order_line._cancel_draft_stock_move()

        return super(SaleOrder, self)._action_cancel()

    def action_open_reservation_entry(self):
        self.ensure_one()
        if self.reservation_entry_id:
            return {
                'name': 'Reservation Entry',
                'view_mode': 'form',
                'res_model': 'account.move',
                'res_id': self.reservation_entry_id.id,
                'type': 'ir.actions.act_window',
                'target': 'current',
            }

    def action_reject_lines(self):
        self.ensure_one()
        action = self.sudo().env.ref('mataa_order_management.action_sol_reject_wizard').read()[0]
        action['context'] = {
            'default_sale_order_id': self.id,
            'manual_rejection': True
        }
        return action

    def action_open_shipment_bill(self):
        self.ensure_one()
        if self.shipment_bill_id:
            return {
                'name': 'Shipment Bill',
                'view_mode': 'form',
                'res_model': 'account.move',
                'res_id': self.shipment_bill_id.id,
                'type': 'ir.actions.act_window',
                'target': 'current',
            }

    def create_wallet_reservation(self):
        self.ensure_one()

        total_wallet_and_e_payments = self.get_e_payment_amount()

        # Check if there are any wallet or e-payments
        if total_wallet_and_e_payments > 0:

            # Get necessary data for the journal entry
            journal = self.company_id.wallet_reservation_journal_id
            account = self.company_id.wallet_reservation_account_id
            partner = self.partner_id
            receivable_account = partner.property_account_receivable_id

            # Create journal entry if journal and account are set
            if journal and account:
                # Create the journal entry
                ref = _('حجز محفظة لطلب مبيعات رقم %s') % self.name
                move_vals = {
                    'journal_id': journal.id,
                    'ref': ref,
                    'line_ids': [
                        # Credit Side (Wallet Reservation Account)
                        (0, 0, {
                            'account_id': account.id,
                            'partner_id': partner.id,
                            'name': ref,
                            'credit': total_wallet_and_e_payments,
                            'debit': 0.0,
                        }),
                        # Debit Side (Customer Receivable Account)
                        (0, 0, {
                            'account_id': receivable_account.id,
                            'partner_id': partner.id,
                            'name': ref,
                            'credit': 0.0,
                            'debit': total_wallet_and_e_payments,
                        }),
                    ]
                }

                # Create and post the journal entry
                move = self.env['account.move'].sudo().create(move_vals)
                move.action_post()
                self.reservation_entry_id = move
                data = {
                    "amount": total_wallet_and_e_payments,
                    "odooOwnerId": str(partner.id),
                    "isOnHold": True,
                    "transactionCode": "reservation_entry-" + str(move.id),
                    "transactionOdooId": "reservation_entry-" + str(move.id),
                    "statement": str(move.ref or "") if move else ""
                }

                WalletService.add_deduction(data)

    def clear_wallet_reservation(self):
        self.ensure_one()
        if not self.reservation_entry_id:
            return

        # Ensure that the reservation entry can be reversed (only posted moves can be reversed)
        if self.reservation_entry_id.state != 'posted':
            raise UserError('The Reservation Entry is not posted and cannot be reversed.')

        # Ensure that the reservation entry was not cleared before
        if self.reservation_entry_id.reversal_move_id:
            raise UserError('The Reservation Entry is already cleared.')

        rv_id = self.env['account.move.reversal'].with_context(
            {'active_model': 'account.move',
             'active_ids': self.reservation_entry_id.ids}).create({'move_ids': self.reservation_entry_id.ids,
                                                                   'journal_id': self.reservation_entry_id.journal_id.id,
                                                                   'reason': 'Wallet reservation clearance'})
        rv_id.reverse_moves()
        WalletService.reset_on_hold(transaction_odoo_id="reservation_entry-" + str(self.reservation_entry_id.id))

    def create_ticket(self):
        self.ensure_one()
        team_id = self.company_id.customer_support_team_id
        if not team_id:
            raise UserError(_("Miss configuration: No customer support team found"))

        ticket_data = {
            'name': 'Order: %s' % self.name,
            'description': """Hello Customer Care Team, Here is a new order to be reviewed""",

            'mataa_customer_id': self.partner_id.id,
            'mataa_so_id': self.id,

            'team_id': team_id.id,
            'company_id': self.company_id.id,
        }

        ticket_id = self.env['helpdesk.ticket'].sudo().create(ticket_data)
        action = {
            'res_model': 'helpdesk.ticket',
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_id': ticket_id.id,
        }
        return action

    def create_order_closing_ticket(self):
        self.ensure_one()
        if self.company_id.order_closing_support_team_id:
            ticket_data = {
                'name': 'Handel %s Order: %s' % (self.mata_shipment_state, self.name),
                'description': """Hello Order Closing Team, Here is a new order to be closed""",

                'mataa_customer_id': self.partner_id.id,
                'mataa_so_id': self.id,

                'team_id': self.company_id.order_closing_support_team_id.id,
                'company_id': self.company_id.id,
            }

            self.env['helpdesk.ticket'].sudo().create(ticket_data)
        activity_res_id = self.env['ir.config_parameter'].sudo().get_param('sale_order.default_res_id')
        activity_type_id = self.env.ref('mail.mail_activity_data_todo')
        if activity_type_id:
            user_id = self.user_id.id
            if not user_id:
                user_id = activity_res_id
                if not user_id:
                    user_id = self.env['res.users'].search([], limit=1).id
            self.env['mail.activity'].create({
                'res_id': self.id,
                'res_model_id': self.env['ir.model']._get_id(self._name),
                'activity_type_id': activity_type_id.id,
                'user_id': user_id,
                'date_deadline': fields.Date.today(self),
                'summary': "Close this order",
            })

    def create_order_closing_activity(self):
        self.ensure_one()
        user_id = self.user_id.id
        if self.company_id.activity_default_res_id:
            user_id = self.company_id.activity_default_res_id.id

        activity_type_id = self.env.ref('mail.mail_activity_data_todo')
        if activity_type_id:
            self.env['mail.activity'].create({
                'res_id': self.id,
                'res_model_id': self.env['ir.model']._get_id(self._name),
                'activity_type_id': activity_type_id.id,
                'user_id': user_id,
                'date_deadline': fields.Date.today(self),
                'summary': "Close this order",
            })

    def get_e_payment_amount(self):
        self.ensure_one()

        # Compute the sum of e-payments and wallet payments
        e_journal_codes = [self.company_id.wallet_reservation_journal_id.code]
        e_journal_codes += self.env['account.journal'].sudo().search([('e_payment_journal', '=', True)]).mapped('code')

        total_wallet_and_e_payments = sum(p.amount for p in self.mataa_payment_ids if p.code in e_journal_codes)

        return total_wallet_and_e_payments

    @api.model_create_multi
    def create(self, vals):

        order_ids = super(SaleOrder, self).create(vals)

        for order_id in order_ids:
            if order_id.mataa_customer_note:
                order_id._apply_note_tag_rules()

        for order_id in order_ids.filtered(lambda o: o.mata_order_id):

            # Compute the sum of e-payments and wallet payments
            e_journal_codes = [order_id.company_id.wallet_reservation_journal_id.code]
            e_journal_codes += self.env['account.journal'].sudo().search([('e_payment_journal', '=', True)]).mapped(
                'code')

            total_wallet_and_e_payments = sum(p.amount for p in order_id.mataa_payment_ids if p.code in e_journal_codes)

            # Check if there are any wallet or e-payments
            if total_wallet_and_e_payments > 0:

                # Get necessary data for the journal entry
                journal = order_id.company_id.wallet_reservation_journal_id
                account = order_id.company_id.wallet_reservation_account_id
                partner = order_id.partner_id
                receivable_account = partner.property_account_receivable_id

                # Create journal entry if journal and account are set
                if journal and account:
                    # Create the journal entry
                    ref = _('حجز محفظة لطلب مبيعات رقم %s  %s') % (order_id.mata_order_id,
                                                                   order_id.mataa_payment_ids and
                                                                   order_id.mataa_payment_ids[
                                                                       0].payment_transaction_id or '')
                    move_vals = {
                        'journal_id': journal.id,
                        'ref': ref,
                        'line_ids': [
                            # Credit Side (Wallet Reservation Account)
                            (0, 0, {
                                'account_id': account.id,
                                'partner_id': partner.id,
                                'name': ref,
                                'credit': total_wallet_and_e_payments,
                                'debit': 0.0,
                            }),
                            # Debit Side (Customer Receivable Account)
                            (0, 0, {
                                'account_id': receivable_account.id,
                                'partner_id': partner.id,
                                'name': ref,
                                'credit': 0.0,
                                'debit': total_wallet_and_e_payments,
                            }),
                        ]
                    }

                    # Create and post the journal entry
                    move = self.env['account.move'].sudo().create(move_vals)
                    move.action_post()
                    order_id.reservation_entry_id = move

                    data = {
                        "amount": total_wallet_and_e_payments,
                        "odooOwnerId": str(partner.id),
                        "isOnHold": True,
                        "transactionCode": "reservation_entry-" + str(move.id),
                        "transactionOdooId": "reservation_entry-" + str(move.id),
                        "statement": ref
                    }
                    WalletService.add_deduction(data)

            inhouse_order = True
            inhouse_order_tag = self.env.ref("mataa_order_management.so_tag_in_house")
            for line in order_id.order_line:
                if line.vendor_id:
                    inhouse_order = False
                    break
            if inhouse_order and inhouse_order_tag:
                order_id.mataa_tag_ids = [(4, inhouse_order_tag.id)]

            IrConfig = self.env['ir.config_parameter'].sudo()
            auto_confirm_enabled = IrConfig.get_param('mataa_order_management.auto_confirm_enabled')
            enable_note = IrConfig.get_param('mataa_order_management.auto_confirm_enable_customer_note')
            amount_limit = float(IrConfig.get_param('mataa_order_management.auto_confirm_amount_limit'))
            order_limit = int(IrConfig.get_param('mataa_order_management.auto_confirm_order_count_limit'))
            check_active = IrConfig.get_param('mataa_order_management.auto_confirm_check_active_order')
            check_refund = IrConfig.get_param('mataa_order_management.auto_confirm_check_refunds')
            excluded_city_ids_str = IrConfig.get_param('mataa_order_management.auto_confirm_excluded_city_ids')
            excluded_city_ids = eval(excluded_city_ids_str) if excluded_city_ids_str else []

            skip_auto_confirm = False

            if not auto_confirm_enabled:
                skip_auto_confirm = True

            if order_id.company_id.auto_confirm_in_house_orders:
                if not inhouse_order:
                    skip_auto_confirm = True

            if enable_note and order_id.mataa_customer_note:
                skip_auto_confirm = True

            if amount_limit and order_id.amount_total > amount_limit:
                skip_auto_confirm = True

            if order_limit:
                customer_orders = self.env['sale.order'].search_count([
                    ('partner_id', '=', order_id.partner_id.id),
                    ('id', '!=', order_id.id)
                ])
                if customer_orders > order_limit:
                    skip_auto_confirm = True

            if check_active:
                active_orders = self.env['sale.order'].search([
                    ('partner_id', '=', order_id.partner_id.id),
                    ('state', '=', 'sale'),
                    ('id', '!=', order_id.id)
                ])
                if active_orders:
                    has_pending_delivery = any(
                        any(
                            p.picking_type_code == 'outgoing' and p.state not in ['done', 'cancel']
                            for p in o.picking_ids
                        )
                        for o in active_orders
                    )
                    if has_pending_delivery:
                        skip_auto_confirm = True

            if check_refund:
                refund_orders = self.env['sale.order'].search([
                    ('partner_id', '=', order_id.partner_id.id),
                    ('is_refund_order', '=', True),
                    ('id', '!=', order_id.id)
                ])
                if refund_orders:
                    has_pending_return = any(
                        any(
                            p.picking_type_code == 'incoming' and p.state not in ['done', 'cancel']
                            for p in o.picking_ids
                        )
                        for o in refund_orders
                    )
                    if has_pending_return:
                        skip_auto_confirm = True

            if excluded_city_ids and order_id.mataa_city_id and order_id.mataa_city_id.id in excluded_city_ids:
                skip_auto_confirm = True

            if not skip_auto_confirm:
                order_id.action_confirm()

        return order_ids

    def action_view_mataa_purchase_orders(self):
        self.ensure_one()
        purchase_order_ids = self.env['purchase.order'].search([('sale_order_id', '=', self.id)]).ids
        action = {
            'res_model': 'purchase.order',
            'type': 'ir.actions.act_window',
        }
        if len(purchase_order_ids) == 1:
            action.update({
                'view_mode': 'form',
                'res_id': purchase_order_ids[0],
            })
        else:
            action.update({
                'name': _("Purchase Order related to %s", self.name),
                'domain': [('id', 'in', purchase_order_ids)],
                'view_mode': 'tree,form',
            })
        return action

    def action_view_mataa_sales_orders(self):
        self.ensure_one()
        sale_order_ids = self.env['sale.order'].search([('partner_id', '=', self.partner_id.id)]).ids
        action = {
            'res_model': 'sale.order',
            'type': 'ir.actions.act_window',
        }
        if len(sale_order_ids) == 1:
            action.update({
                'view_mode': 'form',
                'res_id': sale_order_ids[0],
            })
        else:
            action.update({
                'name': _("Orders related to %s", self.partner_id.name),
                'domain': [('id', 'in', sale_order_ids)],
                'view_mode': 'tree,form',
            })
        return action

    def action_view_mataa_active_sales_orders(self):
        self.ensure_one()
        sale_order_ids = self.env['sale.order'].search([
            ('partner_id', '=', self.partner_id.id),
            ('state', '=', 'sale'),
            ('ecommerce_status', 'not in',
             ['out_shipping', 'out_partially_delivered', 'out_delivered', 'out_returned', 'canceled'])]).ids
        action = {
            'res_model': 'sale.order',
            'type': 'ir.actions.act_window',
        }
        if len(sale_order_ids) == 1:
            action.update({
                'view_mode': 'form',
                'res_id': sale_order_ids[0],
            })
        else:
            action.update({
                'name': _("Active Orders related to %s", self.partner_id.name),
                'domain': [('id', 'in', sale_order_ids)],
                'view_mode': 'tree,form',
            })
        return action

    def action_view_mataa_sales_quotations(self):
        self.ensure_one()
        sale_order_ids = self.env['sale.order'].search(
            [('partner_id', '=', self.partner_id.id), ('state', 'in', ['draft', 'sent'])]).ids
        action = {
            'res_model': 'sale.order',
            'type': 'ir.actions.act_window',
        }
        if len(sale_order_ids) == 1:
            action.update({
                'view_mode': 'form',
                'res_id': sale_order_ids[0],
            })
        else:
            action.update({
                'name': _("Quotations related to %s", self.partner_id.name),
                'domain': [('id', 'in', sale_order_ids)],
                'view_mode': 'tree,form',
            })
        return action

    def action_view_mataa_sales_bundles(self):
        self.ensure_one()
        sale_order_ids = self.mataa_bundle_id.mataa_bundled_so_ids.ids
        action = {
            'res_model': 'sale.order',
            'type': 'ir.actions.act_window',
        }
        if len(sale_order_ids) == 1:
            action.update({
                'view_mode': 'form',
                'res_id': sale_order_ids[0],
            })
        else:
            action.update({
                'name': _("Bundled Orders related to %s", self.partner_id.name),
                'domain': [('id', 'in', sale_order_ids)],
                'view_mode': 'tree,form',
            })
        return action

    def action_view_mataa_related_tickets(self):
        self.ensure_one()
        ticket_ids = self.env['helpdesk.ticket'].search([('mataa_so_id', '=', self.id)]).ids
        action = {
            'res_model': 'helpdesk.ticket',
            'type': 'ir.actions.act_window',
        }
        if len(ticket_ids) == 1:
            action.update({
                'view_mode': 'form',
                'res_id': ticket_ids[0],
            })
        else:
            action.update({
                'name': _("Tickets related to %s", self.partner_id.name),
                'domain': [('id', 'in', ticket_ids)],
                'view_mode': 'tree,form',
            })
        return action

    def action_view_mataa_related_refunds(self):
        self.ensure_one()
        sale_order_ids = self.refund_ids.ids
        action = {
            'res_model': 'sale.order',
            'type': 'ir.actions.act_window',
        }
        if len(sale_order_ids) == 1:
            action.update({
                'view_mode': 'form',
                'res_id': sale_order_ids[0],
            })
        else:
            action.update({
                'name': _("Refunds related to %s", self.name),
                'domain': [('id', 'in', sale_order_ids)],
                'view_mode': 'tree,form',
            })
        return action

    def action_view_mataa_related_payments(self):
        self.ensure_one()
        payment_ids = self.related_account_payment_ids.ids
        action = {
            'res_model': 'account.payment',
            'type': 'ir.actions.act_window',
        }
        if len(payment_ids) == 1:
            action.update({
                'view_mode': 'form',
                'res_id': payment_ids[0],
            })
        else:
            action.update({
                'name': _("Refunds payments to %s", self.name),
                'domain': [('id', 'in', payment_ids)],
                'view_mode': 'tree,form',
            })
        return action

    def action_compensation_wizard(self):
        self.ensure_one()
        return {
            'name': _('Compensation'),
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order.compensation.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_sale_order_id': self.id,
                'default_compensation_amount': self._get_max_compensation_amount(),
            }
        }

    def _get_max_compensation_amount(self):
        self.ensure_one()

        compensation_percentage = self.env['ir.config_parameter'].sudo().get_param(
            'mataa_order_management.compensation_allowable_percentage'
        )
        if not compensation_percentage:
            raise UserError(_('Compensation percentage is not configured.'))
        compensation_percentage = float(compensation_percentage)
        max_amount = self.amount_total * (compensation_percentage / 100.0)

        user = self.env.user
        if user.has_group('sales_team.group_sale_manager'):
            max_amount = self.amount_total

        return max_amount

    #     ========== Utilities ==========

    def add_delivery_method(self, carrier_id, delivery_price):
        self.ensure_one()
        wiz_action = self.action_open_delivery_wizard()
        choose_delivery_carrier = self.env[wiz_action['res_model']].with_context(
            wiz_action['context']).sudo().create({'carrier_id': carrier_id,
                                                  'order_id': self.id})

        choose_delivery_carrier.delivery_price = delivery_price
        choose_delivery_carrier.button_confirm()

    def add_coupon(self, coupon_code):
        status = self._try_apply_code(coupon_code)
        if 'error' in status:
            raise ValidationError(status['error'])
        all_rewards = self.env['loyalty.reward']
        for rewards in status.values():
            all_rewards |= rewards
        print('99*****', all_rewards)
        context = {
            'active_id': self.id,
            'default_reward_ids': all_rewards.ids,
        }

        reward = self.env['sale.loyalty.reward.wizard'].with_context(context).sudo().create({})
        reward.write({
            'selected_reward_id': reward.reward_ids[0].id if reward.reward_ids else False,
        })
        reward.action_apply()

        self._track_coupon_usage(coupon_code)

    def _track_coupon_usage(self, coupon_code):
        """Track coupon usage for customer restrictions"""
        if not self.partner_id:
            return

        programs = self.env['loyalty.program'].search([
            ('rule_ids.code', '=', coupon_code),
            ('active', '=', True)
        ])

        for program in programs:
            for rule in program.rule_ids.filtered(lambda r: r.code == coupon_code):
                rule._create_usage_record(self.partner_id.id, self.id)

    def action_cancel(self):
        # Remove usage records before canceling
        if self.partner_id:
            usage_records = self.env['loyalty.rule.customer.usage'].search([
                ('order_id', '=', self.id),
                ('partner_id', '=', self.partner_id.id)
            ])
            if usage_records:
                _logger.info(f"Removing {len(usage_records)} usage records for cancelled order {self.id}")
                usage_records.unlink()

        return super().action_cancel()

    def action_open_cancel_wizard(self):
        self.ensure_one()
        return {
            'name': _('Cancel Order'),
            'type': 'ir.actions.act_window',
            'res_model': 'order.cancel.wizard',
            'view_mode': 'form',
            'target': 'new',
            'view_id': self.env.ref('mataa_order_management.view_order_cancel_wizard_form').id,
            'context': {
                'active_model': self._name,
                'active_ids': self.ids,
            }
        }

    def _try_apply_code(self, code):
        self.ensure_one()
        _logger.info(f"Applying coupon code '{code}' on order {self.name}")

        if not self.partner_id:
            _logger.warning("No partner on order; skipping coupon validation.")
            return super()._try_apply_code(code)

        programs = self.env['loyalty.program'].search([
            ('rule_ids.code', '=', code),
            ('active', '=', True)
        ])
        _logger.info(f"Found {len(programs)} loyalty programs for code {code}")

        for program in programs:
            matching_rules = program.rule_ids.filtered(lambda r: r.code == code)
            for rule in matching_rules:
                _logger.info(f"Checking rule {rule.display_name} (ID {rule.id}) for eligibility...")

                partner_id = self.partner_id.id
                order_id = self.id

                try:
                    valid = rule._is_valid_for_customer(partner_id=partner_id, order_id=order_id)
                except Exception as e:
                    _logger.error(f"Error during rule._is_valid_for_customer: {e}", exc_info=True)
                    raise ValidationError(_("Unexpected error while validating coupon eligibility."))

                if not valid:
                    _logger.warning(f"Rule {rule.id} rejected coupon for partner {partner_id} order {order_id}")
                    return {
                        'error': _(
                            f'You are not eligible to use this discount code '
                            f'or you have already reached its usage limit ({rule.usage_limit_per_customer}).'
                        )
                    }
        _logger.info(
            f"Checking core for program with code '{code}' -> "
            f"{self.env['loyalty.program'].search([('rule_ids.code', '=', code), ('active', '=', True)]).ids}"
        )
        result = super(SaleOrder, self.with_company(self.company_id))._try_apply_code(code)

        # Track usage only if the code actually applied successfully
        if isinstance(result, dict) and 'error' not in result:
            _logger.info(f"Coupon '{code}' applied successfully; tracking usage.")
            self._track_coupon_usage(code)
        else:
            _logger.warning(f"Coupon '{code}' could not be applied. Result: {result}")

        return result

    def _apply_program_reward(self, program, coupon_or_code=False, **kwargs):
        result = super()._apply_program_reward(program, coupon_or_code, **kwargs)

        rewards = program.reward_ids if hasattr(program, 'reward_ids') else program
        for reward in rewards.filtered(lambda r: r.discount_type == 'percent' and r.max_discount_amount):
            for order in self:
                order_total = order.amount_untaxed
                discount_amount = order_total * (reward.discount_percentage / 100.0)

                if discount_amount > reward.max_discount_amount:
                    discount_amount = reward.max_discount_amount

                _logger.info(
                    f"[Reward {reward.id}] applying capped percentage "
                    f"→ order {order.name}, percent={reward.discount_percentage}%, "
                    f"cap={reward.max_discount_amount}, final_discount={discount_amount}"
                )

                if discount_amount > 0:
                    order.order_line.create({
                        'order_id': order.id,
                        'name': f"{reward.name or 'Discount'} ({reward.discount_percentage}% up to {reward.max_discount_amount})",
                        'price_unit': -discount_amount,
                        'product_uom_qty': 1.0,
                        'is_reward_line': True,
                        'product_id': reward.reward_product_id.id if reward.reward_product_id else False,
                    })

        if self.partner_id and result:
            tracked = set()
            for rule in program.rule_ids:
                if rule.id in tracked:
                    continue
                if rule.code == coupon_or_code or (not coupon_or_code and rule.minimum_qty <= 1):
                    rule._create_usage_record(self.partner_id.id, self.id)

    def action_draft(self):
        """
        Overrides the original action_draft to re-create draft reservations
        when an order is set back to quotation.
        """
        res = super(SaleOrder, self).action_draft()
        for order in self:
            order.order_line._create_draft_stock_move()
        return res

    @api.depends('order_line.inhouse_location')
    def _compute_inhouse_line_count(self):
        """Counts the lines that have an inhouse location value."""
        for order in self:
            inhouse_lines = order.order_line.filtered(lambda line: line.inhouse_location)
            order.inhouse_line_count = len(inhouse_lines)

    @api.depends('order_line.inhouse_location', 'order_line.product_uom_qty')
    def _compute_inhouse_total_qty(self):
        """Calculates the sum of quantities for lines that have an inhouse location value."""
        for order in self:
            inhouse_lines = order.order_line.filtered(lambda line: line.inhouse_location)
            total_quantity = sum(inhouse_lines.mapped('product_uom_qty'))
            order.inhouse_total_qty = total_quantity

    def _apply_note_tag_rules(self):
        """
        adds or removes tags based on the presence of the word in the client's note.
        """
        for order in self:
            rules = self.env['mataa.note.tag.rule'].search([('company_id', '=', order.company_id.id)])
            if not rules:
                continue

            note = order.mataa_customer_note or ''
            note_lower = note.lower()

            tags_to_add = set()
            tags_to_remove = set()

            for rule in rules:
                keyword_lower = rule.keyword.lower()

                if keyword_lower in note_lower:
                    tags_to_add.add(rule.tag_id.id)
                else:
                    tags_to_remove.add(rule.tag_id.id)

            if tags_to_add or tags_to_remove:
                current_tags = set(order.mataa_tag_ids.ids)
                new_tags = (current_tags - tags_to_remove) | tags_to_add

                if current_tags != new_tags:
                    order.mataa_tag_ids = [(6, 0, list(new_tags))]
    
    def action_view_time_taken(self):
        domain = [
            ('mail_message_id.model', '=', 'sale.order'),
            ('mail_message_id.res_id', '=', self.id),
            ('field_id.name', '=', 'mata_order_state'),
        ]
        tree_view_id = self.env.ref('mataa_order_management.view_mataa_order_state_tracking_tree').id
        return {
            'type': 'ir.actions.act_window',
            'name': 'Time Taken',
            'res_model': 'mail.tracking.value',
            'view_mode': 'tree',
            'domain': domain,
            'view_id': tree_view_id,
        }


class MataaSOPayment(models.Model):
    _name = 'mataa.so.payment'
    _description = 'Mataa Sale Order Payment'

    sale_order_id = fields.Many2one(
        'sale.order',
        string='Sale Order',
        required=True,
        help='Select the related Sale Order'
    )

    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        related='sale_order_id.currency_id',
        store=True,
        help='The currency used in the related Sale Order'
    )

    code = fields.Char(
        string='Journal Code',
        help='A journal code for this payment'
    )

    payment_transaction_id = fields.Char(
        string='Transaction ID',
        help='Online Payment Transaction ID'
    )

    payment_transaction_odoo_id = fields.Char(
        string='Transaction Odoo ID',
        help='Odoo ID for an Online Payment Already synced to Odoo (account_payment.id)'
    )
    payment_state = fields.Selection([('success', 'Success'),
                                      ('failed', 'Failed')], default=False, copy=False, tracking=True)

    amount = fields.Monetary(
        string='Amount',
        currency_field='currency_id',
        help='The amount of the payment'
    )
    display_name = fields.Char(compute='_compute_display_name', store=True)

    journal_id = fields.Many2one(
        'account.journal',
        string='Journal',
        compute='_compute_journal_id',
        store=True
    )

    journal_description = fields.Text(
        string="Description",
        readonly=True,
        related='journal_id.payment_method_description'
    )

    @api.depends('code')
    def _compute_journal_id(self):

        for payment in self:
            if payment.code:

                journal = self.env['account.journal'].search([('code', '=', payment.code)], limit=1)
                payment.journal_id = journal.id if journal else False
            else:
                payment.journal_id = False

    @api.depends('code', 'amount')
    def _compute_display_name(self):
        for record in self:
            record.display_name = f"{record.code}: {record.amount}"

    @api.constrains('code')
    def _check_code(self):
        for mataa_payment_id in self:
            if not self.env['account.journal'].search([('code', '=', mataa_payment_id.code)], limit=1):
                raise UserError(_('No journal matched the provided code %s.' % mataa_payment_id.code))

    @api.model_create_multi
    def create(self, vals):
        mataa_payment_ids = super(MataaSOPayment, self).create(vals)

        for mataa_payment_id in mataa_payment_ids:

            journal = self.env['account.journal'].search([('code', '=', mataa_payment_id.code),
                                                          ('e_payment_journal', '=', True)], limit=1)

            if journal:
                ref = _('دفعة الكترونية عن طريق %s مقابل طلب المبيعات رقم %s  %s') % (journal.name,
                                                                                      mataa_payment_id.sale_order_id.mata_order_id,
                                                                                      mataa_payment_id.payment_transaction_id or '')
                partner_id = mataa_payment_id.sale_order_id.partner_id
                amount = mataa_payment_id.amount
                sale_order_id = mataa_payment_id.sale_order_id

                payment_id = self.env['account.payment'].search(
                    [('id', '=', mataa_payment_id.payment_transaction_odoo_id),
                     ('partner_id', '=', partner_id.id)])
                if payment_id and payment_id.amount == mataa_payment_id.amount:
                    payment_id.write({'ref': ref,
                                      'mataa_payment_id': mataa_payment_id.id,
                                      'mataa_sale_order_id': sale_order_id.id})
                elif payment_id:
                    old_amount = payment_id.amount
                    new_amount = mataa_payment_id.amount

                    payment_id.write({
                        'ref': ref,
                        'mataa_payment_id': mataa_payment_id.id,
                        'mataa_sale_order_id': sale_order_id.id
                    })

                    # Create a helpdesk ticket to Finance with the new amount details
                    company = sale_order_id.company_id
                    team = company.refund_support_team_id
                    desc = (
                        "هناك تعارض في قيمة الدفعة الإلكترونية المرتبطة بهذا الطلب.\n\n"
                        f"- رقم الطلب: {sale_order_id.name} / المرجع الداخلي: {sale_order_id.mata_order_id}\n"
                        f"- العميل: {partner_id.display_name} (ID {partner_id.id})\n"
                        f"- معرّف معاملة الدفع: {mataa_payment_id.payment_transaction_id or '—'}\n"
                        f"- معرف ايصال الدفع : {payment_id.id}\n"
                        f"- المبلغ الحالي على دفعة أودو: {old_amount}\n"
                        f"- المبلغ الوارد : {new_amount}\n"
                        f"- الرجاء المراجعة وتعديل الدفعة/الفاتورة حسب الحاجة."
                    )

                    self.env['helpdesk.ticket'].sudo().create({
                        'name': f'مراجعة دفعة إلكترونية لطلب {sale_order_id.name}',
                        'description': desc,
                        'mataa_customer_id': partner_id.id,
                        'mataa_so_id': sale_order_id.id,
                        'team_id': team.id if team else False,
                        'company_id': company.id,
                    })
                else:
                    time_threshold = fields.Datetime.now() - timedelta(minutes=1)

                    potential_duplicate = self.env['account.payment'].search([
                        ('partner_id', '=', partner_id.id),
                        ('amount', '=', amount),
                        ('create_date', '>=', time_threshold),
                    ], limit=1)

                    payment_id = self.env['account.payment'].create({
                        'partner_id': partner_id.id,
                        'journal_id': journal.id,
                        'amount': amount,
                        'ref': ref,
                        'payment_type': 'inbound',
                        'partner_type': 'customer',
                        'mataa_payment_id': mataa_payment_id.id,
                        'mataa_sale_order_id': sale_order_id.id,
                        'sale_order_id': sale_order_id.id
                    })

                    if potential_duplicate:
                        msg = f"تم إبقاء هذه الدفعة كمسودة (Draft) لأن النظام اكتشف دفعة أخرى مشابهة (رقم: {potential_duplicate.name}) تم إنشاؤها حديثاً."
                        payment_id.message_post(body=msg)
                    else:
                        payment_id.action_post()

                mataa_payment_id.sale_order_id.add_payment(payment_id.id)

        return mataa_payment_ids

    def _apply_loyalty_program(self, program):
        result = super()._apply_loyalty_program(program)

        for rule in program.rule_ids:
            if rule.usage_limit_per_customer > 0 and self.partner_id:
                self.env['loyalty.rule.customer.usage'].create({
                    'rule_id': rule.id,
                    'partner_id': self.partner_id.id,
                    'order_id': self.id,
                    'usage_date': fields.Datetime.now()
                })

        return result
