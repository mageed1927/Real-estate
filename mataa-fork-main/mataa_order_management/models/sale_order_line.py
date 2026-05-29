# -*- coding: utf-8 -*-
from string import digits

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from ..services.sale_order_service import SaleOrderSyncService
import logging
from ..services.vms_service import VMSService
from ..services.vendor_notification_service import VendorNotificationService
_logger = logging.getLogger(__name__)



class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    price_unit_before_discount = fields.Monetary(
        string="Before Discount",
        compute="_compute_before_after_units",
        currency_field="currency_id",
        store=False,
    )
    price_unit_after_discount = fields.Monetary(
        string="After Discount",
        compute="_compute_before_after_units",
        currency_field="currency_id",
        store=False,
    )
    mataa_original_price = fields.Monetary(
        string="Mataa Original Price (Before Discount)",
        store=True,
        help="The price of the product before discount, coming from Mataa App."
    )

    mataa_discount_amount = fields.Monetary(
        string="Mataa Discount Amount",
        store=True,
        compute="_compute_mataa_discount_amount",
        help="The difference between Original Price and Unit Price."
    )

    refund_reason_id = fields.Many2one(
        'sale.order.reason',
        string='اRefunc Reasons',
        copy=False,
        domain="[('reason_type', '=', 'refund')]"
    )

    product_mataa_on_hand_qty = fields.Float(
        string="Mataa On Hand",
        related="product_id.mataa_on_hand_qty",
        readonly=True,
        store=False
    )
    product_last_purchase_date = fields.Date(
        string="Last Purchase Date",
        related="product_id.last_purchase_date",
        readonly=True,
        store=False
    )

    @api.depends('mataa_original_price', 'price_unit')
    def _compute_mataa_discount_amount(self):
        for line in self:
            if line.mataa_original_price > line.price_unit:
                line.mataa_discount_amount = line.mataa_original_price - line.price_unit
            else:
                line.mataa_discount_amount = 0.0

    @api.depends(
        'price_unit', 'discount', 'display_type', 'is_downpayment',
        'product_uom_qty',
        'order_id.order_line.price_subtotal',
        'order_id.order_line.display_type',
        'order_id.order_line.is_reward_line',
        'order_id.order_line.is_delivery',
        'order_id.order_line.is_downpayment',
    )
    def _compute_before_after_units(self):
        for line in self:

            if line.display_type or getattr(line, 'is_reward_line', False) \
                    or getattr(line, 'is_delivery', False) or line.is_downpayment:
                line.price_unit_before_discount = 0.0
                line.price_unit_after_discount = 0.0
                continue

            line.price_unit_before_discount = line.price_unit

            qty = line.product_uom_qty or 0.0
            if qty <= 0.0 or not line.order_id:
                line.price_unit_after_discount = line.price_unit
                continue

            order = line.order_id
            base_lines = order.order_line.filtered(
                lambda l: not l.display_type
                          and not getattr(l, 'is_reward_line', False)
                          and not getattr(l, 'is_delivery', False)
                          and not l.is_downpayment
            )
            base_sum = sum(bl.price_subtotal for bl in base_lines)

            coupon_lines = order.order_line.filtered(
                lambda l: not l.display_type and getattr(l, 'is_reward_line', False)
            )
            coupon_total = sum(cl.price_subtotal for cl in coupon_lines)

            allocation = (line.price_subtotal / base_sum) * coupon_total if base_sum else 0.0
            subtotal_after = line.price_subtotal + allocation
            line.price_unit_after_discount = order.currency_id.round(subtotal_after / qty)

    so_line_main_image = fields.Char(string="Image", related="product_id.main_image")

    within_city = fields.Boolean(string='Within City', compute='_compute_within_city', copy=False, store=True)
    vendor_id = fields.Many2one('res.partner', compute='_compute_vendor_id', copy=False, store=True, readonly=False)
    mataa_id = fields.Char(string="Mataa ID", copy=False, readonly=True)
    check_access_to_delete = fields.Boolean(compute="check_to_delete_access",
                                            help="TECHNICAL: Check if we can show the custom delete button")
    reversed_qty = fields.Float(compute="compute_reversed_qty", help="Last in progress related transfer's reserved qty")

    inhouse_location = fields.Char(
        string='Inhouse Location',
        readonly=True,
        copy=False,
        help="Indicates if the product was in the Inhouse location upon confirmation."
    )

    to_order = fields.One2many('order.and.supplier',
        'sale_order_line_id'
    )

    def check_to_delete_access(self):
        for record in self:
            record.check_access_to_delete = record.check_access_rights('unlink', False) \
                                            and record.order_id.state != 'sale'

    status = fields.Selection([
        ('in_to_be_ordered', 'To Be Ordered'),
        ('in_waiting_for_confirmation', 'Waiting for confirmation'),
        ('in_preparing', 'Preparing'), # when the vendor accept the rfq
        ('in_picked_up', 'Picked up'),
        ('in_not_available', 'Not available'), # if no quantity of this product is available in any of the vendors or if all of the supplier refused the RFQ
        ('in_partially_available', 'Partially available'),
        ('available_at_warehouse', 'Available at the warehouse'),
        ('out_picking', 'Picking'),
        ('out_packing', 'Packing'),
        ('out_ready', 'Ready'),
        ('out_handling', 'Handling'),
        ('out_shipping', 'Shipping'),
        ('out_partially_delivered', 'Partially Delivered'),
        ('delivered', 'Delivered'),
        ('out_delivered', 'Delivered'),
        ('out_returned', 'Returned'),
        ('canceled', 'Canceled')
    ], string='Status', default=False)

    mataa_qty_delivered = fields.Float(
        string="Actual Delivered",
        compute='_compute_mataa_qty_delivered',
        default=0.0,
        digits='Product Unit of Measure',
        store=True, readonly=False, copy=False)
    mataa_qty_to_invoice = fields.Float(
        string="Mataa Quantity To Invoice",
        compute='_compute_mataa_qty_to_invoice',
        digits='Product Unit of Measure',
        store=True)


    mataa_product_cost = fields.Monetary(
        string="Product Cost",
        compute='_compute_mataa_product_cost',
        store=True)

    product_default_code = fields.Char('Internal Reference', related='product_template_id.default_code', store=True)
    product_categ_id = fields.Many2one('product.category', related='product_id.categ_id', store=True,
                                       string='Product Category')

    original_product_uom_qty = fields.Float(
        'Original Ordered Quantity',
        readonly=True,
        copy=False,
        help="The initial quantity ordered when the line was created."
    )
    rejection_ids = fields.One2many(
        'sale.order.line.rejection',
        'sale_order_line_id',
        string='Rejections'
    )

    manual_rejected_qty = fields.Float(
        compute='_compute_manual_rejected_qty',
        store=True,
        readonly=True,
        help="Total quantity rejected manually."
    )


    @api.depends(
        'qty_delivered_method','move_ids.state', 'move_ids.scrapped', 'move_ids.quantity', 'move_ids.product_uom',
        'analytic_line_ids.so_line',
        'analytic_line_ids.unit_amount',
        'analytic_line_ids.product_uom_id')
    def _compute_mataa_qty_delivered(self):
        for line in self:
            if line.qty_delivered_method == 'stock_move':
                qty = 0.0
                outgoing_moves, incoming_moves = line._get_outgoing_incoming_moves()
                for move in outgoing_moves:
                    if move.state == 'cancel':
                        continue
                    qty += move.product_uom._compute_quantity(move.quantity, line.product_uom, rounding_method='HALF-UP')
                for move in incoming_moves:
                    if move.state == 'cancel':
                        continue
                    qty -= move.product_uom._compute_quantity(move.quantity, line.product_uom, rounding_method='HALF-UP')
                line.mataa_qty_delivered = qty

    @api.depends('qty_invoiced', 'qty_delivered', 'product_uom_qty', 'state')
    def _compute_mataa_qty_to_invoice(self):
        """
        Compute the quantity to invoice. If the invoice policy is order, the quantity to invoice is
        calculated from the ordered quantity. Otherwise, the quantity delivered is used.
        """
        for line in self:
            if line.state == 'sale' and not line.display_type:
                if line.product_id.invoice_policy == 'order':
                    line.mataa_qty_to_invoice = line.product_uom_qty - line.qty_invoiced
                else:
                    line.mataa_qty_to_invoice = line.mataa_qty_delivered - line.qty_invoiced
            else:
                line.mataa_qty_to_invoice = 0


    @api.onchange('order_line','product_id','product_uom_qty')
    def _onchange_product_variant(self):
        self.update_line_status()
        # for record in self:
        #     for line in record:
        #         if line.product_id and line.product_id.free_qty >= line.product_uom_qty:
        #             line.status = 'available_at_warehouse'
        #         elif line.product_id and line.product_id.free_qty < line.product_uom_qty:
        #             line.status = 'in_not_available'

    @api.depends('order_partner_id')
    def _compute_within_city(self):
        for line_id in self:
            line_id.within_city = line_id.company_id.city == line_id.order_partner_id.city

    @api.depends('product_uom', 'product_uom_qty', 'product_id')
    def _compute_vendor_id(self):
        for line_id in self:
            if not line_id.vendor_id:

                blacklisted_vendors = self.env['product.vendor.blacklist'].search([('product_id', '=', line_id.product_id.id)]).mapped('vendor_id.id')

                line_converted_qty = line_id.product_uom._compute_quantity(line_id.product_uom_qty, line_id.product_id.uom_po_id)

                seller_ids = line_id.product_id.seller_ids.filtered(
                    lambda seller: seller.product_id.id == line_id.product_id.id and
                                   seller.min_qty >= line_converted_qty and
                                   seller.partner_id.id not in blacklisted_vendors
                )
                if seller_ids:
                    seller_id = seller_ids[0]
                    line_id.vendor_id = seller_id.partner_id
                else:
                    line_id.vendor_id = False

    @api.depends('product_id', 'move_ids')
    def compute_reversed_qty(self):
        for line_id in self:
            reversed_qty = 0
            if line_id.move_ids:
                out_move_id = line_id.move_ids[0]
                if out_move_id.state in ('assigned', 'partially_available', 'confirmed'):
                    # OUT Qty
                    reversed_qty = out_move_id.quantity
                elif out_move_id.state == 'waiting':
                    if out_move_id.move_orig_ids:
                        pack_move_id = out_move_id.move_orig_ids[0]
                        if pack_move_id.state in ('assigned', 'partially_available', 'confirmed'):
                            # PACK Qty
                            reversed_qty = pack_move_id.quantity
                        elif pack_move_id.state == 'waiting':
                            if pack_move_id.move_orig_ids:
                                pick_move_id = pack_move_id.move_orig_ids[0]
                                if pick_move_id.state in ('assigned', 'partially_available', 'confirmed'):
                                    # PICK Qty
                                    reversed_qty = pick_move_id.quantity

            line_id.reversed_qty = reversed_qty

    @api.depends('product_id', 'product_uom', 'product_uom_qty')
    def _compute_price_unit(self):
        for line in self:
            if not line.price_unit:
                super(SaleOrderLine, line)._compute_price_unit()
            else:
                continue

    @api.depends('rejection_ids.rejected_qty')
    def _compute_manual_rejected_qty(self):
        for line in self:
            line.manual_rejected_qty = sum(line.rejection_ids.mapped('rejected_qty'))

    @api.depends('product_id')
    def _compute_mataa_product_cost(self):
        if len(self) > 5000:
            self = self.search([('mataa_product_cost', '=', False)], limit=5000)
        for line in self:
            sale_id = line.order_id
            product_id = line.product_id

            bill_line_ids = self.env['account.move.line'].search([
                ('parent_state', '!=', 'cancel'),
                ('purchase_line_id.order_id.sale_order_id', '=', sale_id.id),
                ('product_id', '=', product_id.id)])

            product_cost = product_id.standard_price
            if bill_line_ids:
                posted_bill_line_ids = bill_line_ids.filtered(lambda aml: aml.parent_state == 'posted')
                bill_line_id = posted_bill_line_ids[0] if posted_bill_line_ids else bill_line_ids[0]
                product_cost = bill_line_id.price_unit
            else:
                pol_ids = self.env['purchase.order.line'].search([('order_id.state', '!=', 'cancel'),
                                                                  ('order_id.sale_order_id', '=', sale_id.id),
                                                                  ('product_id', '=', product_id.id)])
                if pol_ids:
                    confirmed_pol_ids = pol_ids.filtered(lambda pol: pol.order_id.state in ['purchase', 'done'])
                    pol_id = confirmed_pol_ids[0] if confirmed_pol_ids else pol_ids[0]
                    product_cost = pol_id.price_unit

            line.mataa_product_cost = product_cost
            line.invoice_lines.write({"mataa_product_cost": product_cost})


    def update_line_status(self):
        storable_lines = self.filtered(lambda l: l.product_id.detailed_type == 'product')

        service_lines = self - storable_lines
        for line in service_lines:
            line.status = False

        for line in storable_lines:
            if line.product_id and ((line.product_id.free_qty >= line.product_uom_qty) or line.move_ids):
                status = 'available_at_warehouse'
                if line.move_ids:
                    out_move_id = line.move_ids[0]
                    out_picking_state = out_move_id.picking_id.state
                    if out_picking_state == 'cancel':
                        status = 'canceled'
                    elif out_picking_state == 'done':
                        status = 'out_shipping'
                        if line.within_city:
                            status = 'out_handling'
                        #status = out_move_id.picking_id.get_carrier_state(status)
                    elif out_picking_state == 'assigned':
                        status = 'out_ready'
                    else:
                        if out_move_id.move_orig_ids:
                            pack_move_id = out_move_id.move_orig_ids[0]
                            out_pack_state = pack_move_id.picking_id.state
                            if out_pack_state == 'assigned':
                                status = 'out_packing'
                            else:
                                if pack_move_id.move_orig_ids:
                                    pick_move_id = pack_move_id.move_orig_ids[0]
                                    out_pick_state = pick_move_id.picking_id.state
                                    if out_pick_state == 'assigned':
                                        status = 'out_picking'
            else:
                # TODO: Manage incoming status here
                status = 'in_to_be_ordered'
            line.status = status

    def _prepare_invoice_line(self, **optional_values):
        res = super(SaleOrderLine, self)._prepare_invoice_line(**optional_values)

        res.update({
            'mataa_original_price': self.mataa_original_price,
            'mataa_discount_amount': self.mataa_discount_amount,
        })

        if self._context.get('use_mataa_qty', False):
            res['quantity'] = self.mataa_qty_to_invoice
        return res


    def unlink(self):

        lines_to_restore = self.filtered(lambda l: l.order_id.state != 'cancel')
        for line in lines_to_restore:
            line.mataa_order_line_process(line.product_uom_qty * -1)

        self._cancel_draft_stock_move()


        for line in self:
            line.mataa_order_line_process(line.product_uom_qty * -1)
            if line.mataa_id:
                raise UserError(_('You cannot delete line generated from Mataa!'))
            if line.order_id and not line.order_id.is_refund_order and line.order_id.mata_order_id and line.product_id.detailed_type != 'service':
                payload = {
                    "add": [],
                    "remove": [line.product_id.id],
                    "update": []
                }
                SaleOrderSyncService.send_so_update(line.order_id.mata_order_id, payload)
        
        orders_to_update = self.mapped('order_id')
        res = super(SaleOrderLine, self).unlink()
        for order in orders_to_update:
            order._update_mataa_payment_amount()
        return res

    @api.model
    def create(self, vals):
        if 'product_uom_qty' in vals and 'original_product_uom_qty' not in vals:
            vals['original_product_uom_qty'] = vals['product_uom_qty']
        line = super(SaleOrderLine, self).create(vals)
        context_mata_order_id = self.env.context.get('mata_order_id')
        skip_sync = (self.env.context.get('skip_external_sync') or context_mata_order_id)

        if not skip_sync:
            if line.order_id and not line.order_id.is_refund_order and line.order_id.mata_order_id:
                payload = {
                    "add": [{
                        "variantOdooId": line.product_id.id,
                        "quantity": line.product_uom_qty
                    }],
                    "remove": [],
                    "update": []
                }
                SaleOrderSyncService.send_so_update(line.order_id.mata_order_id, payload)

        order = line.order_id
        if order.coupon_applied and order.coupon_type in ['fixed_discount', 'percentage_discount']:
            if line.product_id.type != 'service':
                if order.coupon_applied and order.coupon_type == 'fixed_discount' and order.discount_amount > 0:
                    product_lines = order.order_line.filtered(lambda l: l.product_id.type != 'service')
                    total = sum(product_lines.mapped('price_subtotal')) or 1.0

                    total_discount = order.discount_amount

                    for l in product_lines:
                        proportion = l.price_subtotal / total
                        discount_value = proportion * total_discount
                        l.price_unit = (l.price_subtotal - discount_value) / (l.product_uom_qty or 1.0)

                elif order.coupon_type == 'percentage_discount' and order.discount_percentage > 0:
                    line_discount_value = (line.price_subtotal * order.discount_percentage / 100.0)
                    line.price_unit -= line_discount_value / (line.product_uom_qty or 1.0)

        return super(SaleOrderLine, self).create(vals)

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)

        lines._create_draft_stock_move()

        lines.mataa_order_line_process()

        context_mata_order_id = self.env.context.get('mata_order_id')
        skip_sync = (self.env.context.get('skip_external_sync') or context_mata_order_id)

        if not skip_sync:
            for line in lines:
                if line.order_id and not line.order_id.is_refund_order and line.is_delivery != True and line.order_id.mata_order_id:
                    payload = {
                         "add": [{
                            "variantOdooId": line.product_id.id,
                            "quantity": line.product_uom_qty
                            }],
                        "remove": [],
                        "update": []
                    }
                    SaleOrderSyncService.send_so_update(line.order_id.mata_order_id, payload)

        for line in lines:
            order = line.order_id
            if order.coupon_applied and order.coupon_type in ['fixed_discount', 'percentage_discount']:
                if line.product_id.type != 'service':
                    if order.coupon_applied and order.coupon_type == 'fixed_discount' and order.discount_amount > 0:
                        product_lines = order.order_line.filtered(lambda l: l.product_id.type != 'service')
                        total = sum(product_lines.mapped('price_subtotal')) or 1.0

                        total_discount = order.discount_amount

                        for l in product_lines:
                            proportion = l.price_subtotal / total
                            discount_value = proportion * total_discount
                            l.price_unit = (l.price_subtotal - discount_value) / (l.product_uom_qty or 1.0)

                    elif order.coupon_type == 'percentage_discount' and order.discount_percentage > 0:
                        line_discount_value = (line.price_subtotal * order.discount_percentage / 100.0)
                        line.price_unit -= line_discount_value / (line.product_uom_qty or 1.0)
            lines.order_id._update_mataa_payment_amount()

        return lines

    def write(self, vals):
        old_quantities = {}
        if 'product_uom_qty' in vals:
            for line in self:
                old_quantities[line.id] = line.product_uom_qty

        if 'product_uom_qty' in vals or 'product_id' in vals:
            self._cancel_draft_stock_move()

        res = super(SaleOrderLine, self).write(vals)

        if 'product_uom_qty' in vals or 'product_id' in vals:
            self._create_draft_stock_move()

        if 'product_uom_qty' in vals:
            new_qty = vals['product_uom_qty']
            for line in self:
                old_qty = old_quantities.get(line.id)
                if self._context.get('manual_rejection'):
                    if old_qty and new_qty < old_qty:
                        rejected_qty = old_qty - new_qty
                        was_inhouse_available = old_qty <= line.product_id.get_free_qty()
                        self.env['sale.order.line.rejection'].create({
                            'sale_order_line_id': line.id,
                            'rejected_qty': rejected_qty,
                            'was_inhouse_available': was_inhouse_available,
                            'reason': 'Manual rejection',
                            'rejection_date': fields.Datetime.now(),
                            'user_id': self.env.user.id,
                        })
                line.mataa_order_line_process(new_qty - old_qty)
                if new_qty > old_qty and line.order_id.state == "sale":
                    line.confirm_line()


                if line.order_id and not line.order_id.is_refund_order and line.order_id.mata_order_id:
                    payload = {
                        "add": [],
                        "remove": [],
                        "update": [{
                            "variantOdooId": line.product_id.id,
                            "quantity": new_qty
                        }]
                    }
                    SaleOrderSyncService.send_so_update(line.order_id.mata_order_id, payload)
        for line in self:
            line.order_id._update_mataa_payment_amount()
        return res


    def _create_draft_stock_move(self):
        """
        Helper method to create a temporary stock move for reservation.
        """
        for line in self.filtered(lambda l: l.product_id.detailed_type == 'product' and l.product_uom_qty > 0 and l.order_id.state in [ 'draft', 'sent']):
            product = line.product_id
            quantity_ordered = line.product_uom_qty

            available_to_promise = product.get_free_qty()

            qty_to_reserve = max(0, min(quantity_ordered, available_to_promise))

            if qty_to_reserve <= 0:
                continue

            try:
                location_src = line.order_id.warehouse_id.lot_stock_id
                location_dest = self.env['stock.location'].search([('usage', '=', 'customer')], limit=1)

                if not location_src or not location_dest:
                    _logger.warning(
                        f"Could not find source or destination location for draft stock move on SO {line.order_id.name}."
                    )
                    continue

                move = self.env['stock.move'].create({
                    'name': _('Draft Reservation: %s') % line.order_id.name,
                    'product_id': product.id,
                    'product_uom_qty': qty_to_reserve,
                    'product_uom': line.product_uom.id,
                    'location_id': location_src.id,
                    'location_dest_id': location_dest.id,
                    'origin': line.order_id.name,
                    'sale_line_id': line.id,
                })
                move._action_confirm()
            except Exception as e:
                _logger.error(f"Failed to create draft stock move for SO Line {line.id}: {e}")


    def _cancel_draft_stock_move(self):
        """
        Helper method to find and cancel the temporary stock move.
        """
        draft_moves = self.move_ids.filtered(lambda m: not m.picking_id and m.state != 'cancel')
        if draft_moves:
            draft_moves._action_cancel()
            draft_moves.unlink()

    def mataa_order_line_process(self, manual_qty=False):
        for line in self:
            # Inhouse Location Check
            try:
                inhouse_loc = self.env['stock.location'].search([('complete_name', '=', 'WH/Stock/Inhouse')], limit=1)
                if inhouse_loc and line.product_id.type == 'product':
                    product_ctx = line.product_id.with_context(location=inhouse_loc.id)
                    if product_ctx.qty_available > 0:
                        line.write({'inhouse_location': inhouse_loc.display_name})
            except Exception as e:
                _logger.error(f"Error in inhouse location check: {e}")

            if line.product_id.detailed_type == 'product':
                qty_to_process = manual_qty if manual_qty is not False else line.product_uom_qty
                if line.product_uom_qty <= 0:
                    continue
                
                if qty_to_process == 0:
                    continue
                elif qty_to_process < 0 and line.order_id.state in ["sale"]:
                    purchase_lines = self.env['purchase.order.line'].sudo().search([
                        ('product_id', '=', line.product_id.id),
                        ('order_id.sale_order_id', '=', line.order_id.id)
                    ])
                    for purchase_line in purchase_lines:
                        qty_update = min((qty_to_process * -1), purchase_line.product_qty)
                        vendor = self.env['product.supplierinfo'].sudo().search([
                            ('partner_id', '=', purchase_line.order_id.partner_id.id),
                            ('product_id', '=', line.product_id.id)
                        ])
                        vendor.sudo().write({
                            'min_qty': vendor.min_qty + qty_update
                        })
                        qty_to_process += qty_update
                        if qty_to_process >= 0:
                            break
                elif qty_to_process < 0:
                    for rec in line.to_order:
                        qty_update = min((qty_to_process * -1), rec.quantity)
                        vendor = rec.product_supplierinfo_id
                        vendor.sudo().write({
                            'min_qty': vendor.min_qty + qty_update
                        })
                        rec.sudo().write({
                            'quantity': rec.quantity - qty_update
                        })
                        qty_to_process += qty_update
                        if qty_to_process >= 0:
                            break
                else:
                    product_in_stock = self.env['stock.quant'].search([
                        ('product_id', '=', line.product_id.id),
                        ("location_id.usage", "=", "internal"),
                    ])
                    total_available = sum(stock.available_quantity for stock in product_in_stock)

                    if total_available < qty_to_process:
                        qty_to_be_ordered = qty_to_process - max(total_available, 0)

                        vendors = self.env['product.supplierinfo'].search([
                            ('product_id', '=', line.product_id.id),
                            ('published', '=', True)
                        ], order='sequence')

                        for vendor in vendors:
                            if qty_to_be_ordered <= 0:
                                break
                            if vendor.min_qty <= 0:
                                continue
                            
                            qty_to_order = min(qty_to_be_ordered, (vendor.min_qty))
                            vendor.write({
                                'min_qty': vendor.min_qty - qty_to_order
                            })
                            line.to_order.create({
                                'product_supplierinfo_id': vendor.id,
                                'quantity': qty_to_order,
                                'sale_order_line_id': line.id
                            })
                            qty_to_be_ordered -= qty_to_order


    def confirm_line(self):
        for line in self:
            for rec in line.to_order:
                vendor = rec.product_supplierinfo_id
                qty_to_order = rec.quantity

                purchase_order = self.env['purchase.order'].search([
                    ('partner_id', '=', vendor.partner_id.id),
                    ('sale_order_id', '=', line.order_id.id)
                ])
                if not purchase_order:
                    purchase_order = self.env['purchase.order'].create({
                                'partner_id': vendor.partner_id.id,
                                'sale_order_id': line.order_id.id,
                                'origin': line.order_id.name
                            })
                    VendorNotificationService.notify_new_rfq_created(vendor_id=vendor.partner_id.id, rfq_id=purchase_order.id)
                
                self.env['purchase.order.line'].create({
                            'order_id': purchase_order.id,
                            'product_id': line.product_id.id,
                            'product_qty': qty_to_order,
                            'price_unit': vendor.price or line.product_id.standard_price,
                            'date_planned': fields.Datetime.now(),
                            'name': line.product_id.display_name,
                        })
            line.to_order.unlink()


class OrderAndSupplier(models.Model):
    _name = 'order.and.supplier'
    _description = '''
        Custom many to many relation between sale order line and product supplierinfo.
    '''
    _log_access = False

    sale_order_line_id = fields.Many2one('sale.order.line')
    product_supplierinfo_id = fields.Many2one('product.supplierinfo')

    quantity = fields.Float(string='Quantity')

    @api.model_create_multi
    def create(self, vals):
        for rec in vals:
            existing_record = self.search([
                ('sale_order_line_id', '=', rec.get('sale_order_line_id')),
                ('product_supplierinfo_id', '=', rec.get('product_supplierinfo_id'))
            ])
            if existing_record:
                existing_record.write({
                    'quantity': existing_record.quantity + vals.get('quantity')
                })
                return existing_record
            else:
                return super(OrderAndSupplier, self).create(vals)
