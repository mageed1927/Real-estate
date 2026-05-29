# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_round


class Picking(models.Model):
    _inherit = "stock.picking"

    state = fields.Selection(
        selection_add=[
            ('verified', 'Verified'),
            ('done',),
        ],
    )

    mataa_sale_order_id = fields.Many2one('sale.order', string='SO', compute='_compute_mataa_sale_order_id', store=True, copy=False)
    mataa_bundle_id = fields.Many2one('so.bundle', string='SO Bundle', copy=False, related='mataa_sale_order_id.mataa_bundle_id', store=True)
    mataa_tag_ids = fields.Many2many('so.tag', string='SO Tags', compute='_compute_mataa_tag_ids')
    customer_tag_ids = fields.Many2many('res.partner.category', string='Customer Tags', compute='_compute_customer_tag_ids')

    note = fields.Html('Notes', compute='_compute_mataa_note', store=True, readonly=False)
    mataa_tickets_count = fields.Integer(compute='compute_mataa_tickets_count')
    mataa_bundles_count = fields.Integer(compute='compute_mataa_bundles_count')

    total_received_value = fields.Monetary(
        string='Total Price Received',
        compute='_compute_total_received_value',
        store=False,
        currency_field='currency_id',
    )
    currency_id = fields.Many2one(
        'res.currency',
        related='company_id.currency_id',
        string='Currency',
    )

    allow_done_exceed_demand = fields.Boolean(
        string="Set Demand equal to Done ",
    )
    return_destination_package_id = fields.Many2one(
        'stock.quant.package',
        string='Return Destination Package',
        copy=False,
        readonly=True,
    )

    on_hold = fields.Boolean(
        related='mataa_sale_order_id.is_suspended',
        store=False,
        string="On Hold",
        readonly=True
    )

    total_received_qty = fields.Float(
        string="Total received quantity",
        compute='_compute_total_received_qty',
        store=False,
        readonly=True
    )

    # TODO: Validation Needed
    # def button_validate(self):
    #     for rec in self:
    #         validated = super(Picking, rec.with_context(skip_backorder=True)).button_validate()
    #         new_record = rec.env['stock.picking'].search([
    #             ('location_id', '=', rec.location_dest_id.id),
    #             ('origin', '=', rec.origin),
    #             ('group_id', '=', rec.group_id.id)
    #         ])
    # 
    #         new_record.partner_id = rec.partner_id.id
    # 
    #     return validated

    @api.depends('move_ids.quantity')
    def _compute_total_received_qty(self):
        for picking in self:
            picking.total_received_qty = sum(picking.move_ids.mapped('quantity'))
            
    @api.depends('move_ids.state', 'move_ids.picked', 'move_type')
    def _compute_state(self):
        verified_ids = set()
        for picking in self:
            if picking.id and picking.state == 'verified':
                verified_ids.add(picking.id)

        super()._compute_state()
        for picking in self:
            if picking.id in verified_ids and picking.state not in ('done', 'cancel'):
                picking.state = 'verified'

    def action_verify(self):
        """Move picking from 'assigned' (Ready) to 'verified' (Verified). Only for incoming receipts."""
        for picking in self:
            if picking.state != 'assigned':
                raise UserError(
                    _('Only pickings in "Ready" state can be verified. '
                      'Current state of %s is "%s".') % (picking.name, picking.state)
                )
            picking.state = 'verified'
        return True

    @api.depends('group_id')
    def _compute_mataa_sale_order_id(self):
        for picking in self:
            sale_order_ids = picking.mapped('group_id.sale_id')
            if sale_order_ids:
                picking.mataa_sale_order_id = sale_order_ids[0].id
            else:
                picking.mataa_sale_order_id = False

    @api.depends('mataa_sale_order_id', 'mataa_sale_order_id.internal_note', 'mataa_sale_order_id.mataa_customer_note')
    def _compute_mataa_note(self):
        for picking in self:
            so_id = picking.mataa_sale_order_id
            picking.note = "<b>Internal Note:</b> %s <br/> <b>Customer Note:</b> %s" % (so_id.internal_note, so_id.mataa_customer_note)

    @api.depends('group_id')
    def _compute_mataa_tag_ids(self):
        for picking in self:
            sale_order_ids = picking.mapped('group_id.sale_id')
            picking.mataa_tag_ids = sale_order_ids.mataa_tag_ids

    @api.depends('group_id')
    def _compute_customer_tag_ids(self):
        for picking in self:
            sale_order_ids = picking.mapped('group_id.sale_id')
            picking.customer_tag_ids = sale_order_ids.mapped('partner_id.category_id')

    def compute_mataa_tickets_count(self):
        for record in self:
            so_id = record.mataa_sale_order_id
            tickets = self.env['helpdesk.ticket'].search([('mataa_so_id', '!=', False), ('mataa_so_id', '=', so_id.id)])
            record.mataa_tickets_count = len(tickets)

    def compute_mataa_bundles_count(self):
        for record in self:
            so_ids = record.mataa_sale_order_id.mataa_bundle_id.mataa_bundled_so_ids - record.mataa_sale_order_id
            record.mataa_bundles_count = len(so_ids)


    def action_detailed_operations(self):
        action = super().action_detailed_operations()
        if self.state == 'verified':
            ctx = dict(action.get('context', {}))
            ctx['create'] = False
            ctx['edit'] = False
            action['context'] = ctx
        return action

    def action_print_related_invoice(self):
        if len(self) != 1:
            raise UserError("Related invoice can only be printed for one Picking")
        if not self.sale_id:
            raise UserError("Picking must have an sale order")
        invoice_id = self.sale_id.invoice_ids.filtered(lambda invoice: invoice.state == "posted")
        if invoice_id:
            return self.env.ref('mataa_order_management.mataa_account_invoices').report_action(invoice_id)
        return self.env.ref('mataa_order_management.mataa_sales_order').report_action(self.sale_id)

    def action_open_label_type(self):
        action = super(Picking, self).action_open_label_type()
        ctx = action.get('context', {})
        shipment_code =  ', '.join(self.mapped('carrier_tracking_ref'))
        if shipment_code:
            ctx.update({"default_extra_html": 'Shipment Code: ' + ', '.join(self.mapped('carrier_tracking_ref'))})
        return action

    def action_view_mataa_sales_bundles(self):
        self.ensure_one()
        sale_order_ids = self.mataa_sale_order_id.mataa_bundle_id.mataa_bundled_so_ids.ids
        action = {
            'res_model': 'sale.order',
            'type': 'ir.actions.act_window',
        }
        if len(sale_order_ids) == 1:
            action.update({
                'view_mode': 'form',
                'res_id': sale_order_ids[0],
                'views': [(False, 'form')],
            })
        else:
            action.update({
                'name': _("Bundled Orders related to %s", self.partner_id.name),
                'domain': [('id', 'in', sale_order_ids)],
                'view_mode': 'tree,form',
                'views': [(False, 'tree'), (False, 'form')],
            })
        return action

    def button_validate(self):
        for picking_id in self:
            if picking_id.on_hold and 2 < picking_id.picking_type_id.id < 6:
                raise UserError("This Opetation is on hold. You can review the control team for information.")
            if (
                    picking_id.picking_type_id.sequence_code == "PACK"
                    and not self._context.get("skip_pack_validate_wizard")
                    and not self._context.get("barcode_trigger")
            ):
                so_id = picking_id.group_id.sale_id
                if not (so_id and so_id.mataa_bundle_id):
                    return picking_id.button_validate_with_wizard()

            out_pickings_to_process = picking_id.move_ids.move_dest_ids.picking_id.filtered(
                lambda p: p.picking_type_id.code == 'outgoing' and p.state != 'done'
            )

            if picking_id.picking_type_id.code == "internal" and picking_id.allow_done_exceed_demand:
                for move in picking_id.move_ids:
                    done_qty = sum(move.move_line_ids.mapped("qty_done"))
                    if done_qty > move.product_uom_qty:
                        move.product_uom_qty = done_qty

            else:
                sm_ids = picking_id.move_ids.filtered(lambda sm: sm.quantity > sm.product_uom_qty)
                if sm_ids:
                    raise UserError("You can not validate this Picking since the Quantity is more than the Demand")

            if not picking_id.carrier_tracking_ref:
                if picking_id.picking_type_id.sequence_code == "PACK":
                    pack_picking_ids = self.env['stock.picking']

                    so_id = picking_id.group_id.sale_id
                    if so_id and so_id.mataa_bundle_id:
                        bundled_so_ids = so_id.mataa_bundle_id.mataa_bundled_so_ids - so_id

                        if bundled_so_ids:
                            if not self._context.get('skip_bundle_pack_confirmation', False) and not self._context.get('barcode_trigger', False):
                                order_list = '\n - '.join(bundled_so_ids.mapped('name'))
                                return picking_id.pack_conformation_action(order_list)

                        pack_picking_ids = bundled_so_ids.mapped('picking_ids').filtered(lambda p: p.picking_type_id.sequence_code == "PACK" and p.state == "assigned")
                        if len(pack_picking_ids) != len(bundled_so_ids):
                            raise UserError(f"There are {len(bundled_so_ids)} 'Bundled Orders' and {len(pack_picking_ids)} 'Ready Pack Transfers'. \n Please check your PACK transfers status.")

                    move_dest_ids = picking_id.move_ids.mapped('move_dest_ids').filtered(lambda dest_id: dest_id.sale_line_id)

                    if not move_dest_ids:
                        sale_order_id = picking_id.move_ids.mapped('move_dest_ids.sale_line_id.order_id')
                        if sale_order_id and sale_order_id[0].is_replacement_order:
                            move_dest_ids = picking_id.move_ids.mapped('move_dest_ids').filtered(lambda dest_id: dest_id.sale_line_id)

                    if move_dest_ids:
                        carrier_id = picking_id.carrier_id
                        if not carrier_id:
                            raise UserError(_('Please assign a Carrier to this transfer.'))

                        method_name = '%s_send_shipping' % carrier_id.delivery_type
                        if not hasattr(carrier_id, method_name):
                            raise UserError(_('Carrier API not available.'))

                        if carrier_id.delivery_type == 'dms':
                            # Build bundled orders for DMS (combined shipment logic lives in the carrier)
                            so_id = picking_id.group_id.sale_id
                            bundled_sale_orders = self.env['sale.order']
                            if so_id and so_id.mataa_bundle_id:
                                bundled_sale_orders = so_id.mataa_bundle_id.mataa_bundled_so_ids

                            # Call DMS directly, passing bundle + extra packs in context
                            carrier_id.with_context(
                                bundled_sale_orders=bundled_sale_orders,
                                extra_bundled_packs=pack_picking_ids and pack_picking_ids.ids
                            ).dms_send_shipping(picking_id)
                        else:
                            # Non-DMS carriers keep the old generic dispatch
                            getattr(
                                carrier_id.with_context(
                                    extra_bundled_packs=pack_picking_ids and pack_picking_ids.ids
                                ),
                                method_name
                            )(picking_id)

                        # Sync OUT picking with tracking + shipment info
                        out_picking_id = move_dest_ids.mapped('picking_id')
                        out_picking_id.carrier_id = carrier_id
                        out_picking_id.carrier_tracking_ref = picking_id.carrier_tracking_ref

                        # camex Info
                        if carrier_id.delivery_type == "camex":
                            out_picking_id.camex_shipment_id = picking_id.camex_shipment_id
                            out_picking_id.camex_shipment_trace_id = picking_id.camex_shipment_trace_id
                        # line Info
                        if carrier_id.delivery_type == "line":
                            out_picking_id.line_shipment_id = picking_id.line_shipment_id

                        related_pickings = self.env['stock.picking'].search([
                            ('group_id', '=', picking_id.group_id.id),
                            ('picking_type_id.sequence_code', 'in', ['PICK', 'PACK', 'OUT']),
                            ('state', '!=', 'done'),
                        ])
                        related_pickings.write({
                            'carrier_tracking_ref': picking_id.carrier_tracking_ref,
                            'camex_shipment_id': picking_id.camex_shipment_id,
                            'camex_shipment_trace_id': picking_id.camex_shipment_trace_id,
                            'line_shipment_id': picking_id.line_shipment_id,
                        })
                        if pack_picking_ids:
                            pack_picking_ids.write({
                                'carrier_id': carrier_id.id,
                                'carrier_tracking_ref': picking_id.carrier_tracking_ref or f"Same as {picking_id.name}",
                                'camex_shipment_id': picking_id.camex_shipment_id,
                                'camex_shipment_trace_id': picking_id.camex_shipment_trace_id,
                                'line_shipment_id': picking_id.line_shipment_id,
                            })

                        out_picks = pack_picking_ids.mapped('move_ids.move_dest_ids.picking_id').filtered(
                            lambda p: p.picking_type_id.sequence_code == 'OUT' and p.state != 'done'
                        )
                        out_picks.write({
                            'carrier_id': carrier_id.id,
                            'carrier_tracking_ref': picking_id.carrier_tracking_ref or f"Same as {picking_id.name}",
                            'camex_shipment_id': picking_id.camex_shipment_id,
                            'camex_shipment_trace_id': picking_id.camex_shipment_trace_id,
                            'line_shipment_id': picking_id.line_shipment_id,
                        })


                        pack_picking_ids.button_validate()

            if out_pickings_to_process:
                out_pickings_to_process.invalidate_recordset(['state'])
                out_pickings_to_process._add_to_carrier_batch()

        res = super(Picking, self).button_validate()

        sale_order_ids = self.mapped('group_id.sale_id')
        sale_order_ids.update_mataa_status()
        sale_order_ids.mapped('order_line').update_line_status()
        sale_order_ids.update_order_stage()

        for rec in self:

            if rec.picking_type_code == 'incoming' and rec.purchase_id:
                vendor = rec.purchase_id.partner_id
                if hasattr(vendor, 'vendor_type') and vendor.vendor_type == 'standard':
                    try:
                        rec.purchase_id.action_create_invoice()

                        bills = rec.purchase_id.invoice_ids.filtered(
                            lambda inv: inv.state == 'draft' and inv.move_type == 'in_invoice'
                        )

                        for bill in bills:
                            if rec.date_done:
                                bill.invoice_date = rec.date_done.date()
                            else:
                                bill.invoice_date = fields.Date.today()

                            if not bill.ref:
                                bill.ref = rec.purchase_id.name

                            bill.action_post()

                        rec.message_post(body=_("System: Vendor Bill created automatically."))
                    except Exception as e:
                        rec.message_post(body=_("Warning: Failed to auto-create bill: %s") % str(e))

            if rec.picking_type_id.code == 'incoming' and rec.return_id and rec.return_id.picking_type_id.code == 'outgoing' and rec.group_id.sale_id:
               rec.create_return_next_picking()

            # If the customer-last-return-picking is validated
            if rec.location_dest_id.id == self.company_id.mataa_return_location_id.id:
                # If the customer return picking is validated, then create return to vendor IN-Pickings
                purchase_moves_by_picking = {}
                for move in rec.move_ids:
                    order_id = move.sale_line_id.order_id
                    if not order_id:
                        orig_moves = move.move_orig_ids
                        if orig_moves:
                            sale_line_id = orig_moves[0].sale_line_id or (
                                    orig_moves[0].move_orig_ids and orig_moves[0].move_orig_ids[0].sale_line_id
                            )
                            order_id = move.sale_line_id.order_id
                    if order_id.is_refund_order:
                        order_id = order_id.refunded_order_id

                    purchase_move_id = self.env['stock.move'].search([('purchase_line_id.order_id.sale_order_id', '=', order_id.id),
                                                            ('product_id', '=', move.product_id.id),
                                                            ('picking_id.state', '=', 'done')], limit=1)
                    if purchase_move_id:
                        if purchase_moves_by_picking.get(purchase_move_id.picking_id.id, False):
                            purchase_moves_by_picking[purchase_move_id.picking_id.id].append(purchase_move_id.id)
                        else:
                            purchase_moves_by_picking[purchase_move_id.picking_id.id] = [purchase_move_id.id]
                #rec.create_return_to_vendor_pickings(purchase_moves_by_picking)

        return res

    def action_resend_shipment(self):
        self.ensure_one()
        if self.picking_type_id.code != 'outgoing':
            raise UserError(_("This picking is not Outgoing."))
        if self.state != 'done':
            raise UserError(_("This picking is not done."))
        if not self.carrier_id:
            raise UserError(_("This picking does not have a carrier."))

        so = self.mataa_sale_order_id or self.sale_id or self.group_id.sale_id
        if not so:
            raise UserError(_("No sale order found for this picking."))

        carrier_name = (self.carrier_id.name or '').strip()
        is_camex = carrier_name == 'Camex' or self.carrier_id.delivery_type == 'camex'
        is_dms = carrier_name == 'DMS Delivery' or self.carrier_id.delivery_type == 'dms'

        if not (is_camex or is_dms):
            raise UserError(_("Unsupported carrier for resend. Only 'DMS Delivery' or 'Camex' are allowed."))

        if not (is_camex or so.dms_shipment_status == 'out_returned'):
            raise UserError(_("Shipment can only be resent after receiving it from delivery carrier."))

        bundled_sale_orders = so.mataa_bundle_id.mataa_bundled_so_ids if so.mataa_bundle_id else None
        extra_bundled_packs = None
        if bundled_sale_orders:
            extra_bundled_packs = self.env['stock.picking'].search([
                ('mataa_sale_order_id', 'in', (bundled_sale_orders - so).mapped('id')),
                ('picking_type_id.sequence_code', '=', 'PACK'),
                ('state', '=', 'done'),
            ])

        old_tracking_ref = self.carrier_tracking_ref

        # Force creating a brand-new shipment even if one already exists.
        vals_to_reset = {'carrier_tracking_ref': False}
        if self.carrier_id.delivery_type == 'camex':
            vals_to_reset.update({
                'camex_shipment_id': False,
                'camex_shipment_trace_id': False,
                'camex_shipment_state': False,
            })
        if hasattr(self, 'dms_shipment_id'):
            vals_to_reset.update({'dms_shipment_id': False})
        self.write(vals_to_reset)

        # Reset sale order shipment states as requested.
        if is_dms:
            so.write({'dms_shipment_status': 'pending'})
        if is_camex:
            so.write({'camex_shipment_state': False})

        method_name = '%s_send_shipping' % self.carrier_id.delivery_type
        if not hasattr(self.carrier_id, method_name):
            raise UserError(_('Carrier API not available.'))

        ctx = {
            'is_resend': True,
        }
        if bundled_sale_orders:
            ctx['bundled_sale_orders'] = bundled_sale_orders.mapped('id')
            ctx['extra_bundled_packs'] = extra_bundled_packs.mapped('id')

        getattr(self.carrier_id.with_context(**ctx), method_name)(self)

        if old_tracking_ref and self.carrier_tracking_ref:
            self.message_post(body=_("Shipment resent. Old tracking: %s → New tracking: %s") % (old_tracking_ref, self.carrier_tracking_ref))
        elif self.carrier_tracking_ref:
            self.message_post(body=_("Shipment resent. New tracking: %s") % self.carrier_tracking_ref)

    def button_validate_with_wizard(self):
        """Entry point from the UI & Barcode: show wizard only for PACK, else behave as original."""
        self.ensure_one()

        if self.picking_type_id.sequence_code != "PACK":
            return self.button_validate()

        carrier = self.carrier_id
        is_dms = bool(carrier and carrier.delivery_type == "dms")

        # --------------------------------------------------
        # 1️⃣ BUNDLE CONFIRMATION — ALWAYS FIRST (ALL carriers)
        # --------------------------------------------------
        if not self._context.get("skip_bundle_pack_confirmation", False):
            so = self.group_id.sale_id
            if so and so.mataa_bundle_id:
                bundled_so_ids = so.mataa_bundle_id.mataa_bundled_so_ids - so
                if bundled_so_ids:
                    order_list = "\n - ".join(bundled_so_ids.mapped("name"))
                    return self.pack_conformation_action(order_list)

        # --------------------------------------------------
        # 2️⃣ DMS → NEVER show print wizard
        # --------------------------------------------------
        if is_dms:
            return self.with_context(skip_pack_validate_wizard=True).button_validate()

        # --------------------------------------------------
        # 3️⃣ NON-DMS → show print delivery note wizard
        # --------------------------------------------------
        if not self._context.get("skip_pack_validate_wizard") and not self._context.get("barcode_trigger"):
            view = self.env.ref('mataa_order_management.picking_validate_print_wizard_view')
            return {
                'name': _('Confirm Validation'),
                'type': 'ir.actions.act_window',
                'res_model': 'picking.validate.print.wizard',
                'view_mode': 'form',
                'views': [(view.id, 'form')],
                'view_id': view.id,
                'target': 'new',
                'context': {
                    'active_id': self.id,
                    'active_model': 'stock.picking',
                },
            }

        # --------------------------------------------------
        # 4️⃣ Fallback
        # --------------------------------------------------
        return self.button_validate()
    def pack_conformation_action(self, order_list):
        self.ensure_one()
        wizard_id = self.env['bundle.pack.confirmation.wizard'].create({
            'msg': f"All bundled orders will be validated:\n {order_list}",
            'pack_picking_id': self.id
        })
        return {
            'name': 'Bundle PACKs Validation',
            'view_mode': 'form',
            'res_model': 'bundle.pack.confirmation.wizard',
            'res_id': wizard_id.id,
            'type': 'ir.actions.act_window',
            'target': 'new',
            'views': [(False, 'form')],  # Added views to prevent JS error
        }

    def _add_to_carrier_batch(self):
        batch_carrier_id_str = self.env['ir.config_parameter'].sudo().get_param(
            'mataa_order_management.batch_carrier_id')

        if not batch_carrier_id_str:
            return

        batch_carrier_id = int(batch_carrier_id_str)

        pickings_to_batch = self.filtered(
            lambda p: p.picking_type_id.code == 'outgoing' and \
                      p.carrier_id.id == batch_carrier_id and \
                      not p.batch_id
        )

        if not pickings_to_batch:
            return

        Batch = self.env['stock.picking.batch']
        batch = Batch.search([
            ('state', 'in', ['draft', 'in_progress']),
            ('carrier_id', '=', batch_carrier_id),
        ], limit=1)

        if not batch:
            batch = Batch.create({'carrier_id': batch_carrier_id})

        pickings_to_batch.batch_id = batch.id

    def write(self, vals):
        if 'batch_id' in vals:
            target_batch = self.env['stock.picking.batch'].browse(vals['batch_id']) if vals['batch_id'] else False
            if target_batch and target_batch.is_customer_return_batch and target_batch.return_batch_state != 'open':
                raise UserError(_("You cannot add pickings to a verified customer return batch."))
            locked_batches = self.mapped('batch_id').filtered(
                lambda batch: batch.is_customer_return_batch and batch.return_batch_state != 'open'
            )
            if locked_batches and vals['batch_id'] != locked_batches[:1].id:
                raise UserError(_("You cannot remove pickings from a verified customer return batch."))
        res = super(Picking, self).write(vals)
        if 'state' in vals:
            sale_order_ids = self.mapped('group_id.sale_id')
            sale_order_ids.update_mataa_status()
            sale_order_ids.mapped('order_line').update_line_status()
        return res

    def create_return_next_picking(self):
        self.ensure_one()

        if self.location_dest_id.id == self.company_id.mataa_return_location_id.id:
            return

        picking_type, inhouse_location = self._get_customer_return_configuration()
        source_location = self.return_id.location_id or self.location_dest_id
        batch = self.env['stock.picking.batch'].get_or_create_open_return_batch(picking_type)

        new_picking = self.copy({
            'move_ids': [(5, 0, 0)],
            'move_line_ids': [(5, 0, 0)],
            'batch_id': batch.id,
            'picking_type_id': picking_type.id,
            'state': 'draft',
            'location_id': source_location.id,
            'location_dest_id': inhouse_location.id,
            'partner_id': self.partner_id.id,
            'return_id': self.return_id.id,
            'origin': _("Customer Return Batch - Return of %s", self.return_id.name),
            'group_id': self.group_id.id,
            'mataa_sale_order_id': self.mataa_sale_order_id.id,
            'note': _(
                "Customer Return Batch\n"
                "Source Return Picking: %(return_picking)s\n"
                "Batch: %(batch)s"
            ) % {
                'return_picking': self.name,
                'batch': batch.name,
            },
        })
        new_picking.message_post_with_source(
            'mail.message_origin_link',
            render_values={'self': new_picking, 'origin': self.return_id},
            subtype_xmlid='mail.mt_note',
        )
        new_picking.message_post(body=_("Customer return internal transfer created for batch %s.") % batch.name)
        move_destinations = {}
        for move in self.move_ids.filtered(lambda m: m.quantity):
            destination_location, destination_package = self._get_customer_return_destination(
                move.product_id,
                move.sale_line_id,
            )
            new_move = move.copy({
                'picking_id': new_picking.id,
                'move_line_ids': [(5, 0, 0)],
                'state': 'draft',
                'date': fields.Datetime.now(),
                'location_id': new_picking.location_id.id,
                'location_dest_id': destination_location.id,
                'picking_type_id': new_picking.picking_type_id.id,
                'warehouse_id': new_picking.picking_type_id.warehouse_id.id,
            })
            move_destinations[new_move.id] = {
                'location_id': destination_location.id,
                'package_id': destination_package.id if destination_package else False,
            }

        new_picking.action_confirm()
        new_picking.action_assign()

        for move in new_picking.move_ids:
            destination = move_destinations.get(move.id)
            if not destination:
                continue
            move.write({'location_dest_id': destination['location_id']})
            if not move.move_line_ids:
                self.env['stock.move.line'].create({
                    'move_id': move.id,
                    'picking_id': new_picking.id,
                    'product_id': move.product_id.id,
                    'product_uom_id': move.product_uom.id,
                    'location_id': move.location_id.id,
                    'location_dest_id': destination['location_id'],
                    'quantity': move.product_uom_qty,
                    'result_package_id': destination['package_id'],
                    'company_id': move.company_id.id,
                })
            else:
                move.move_line_ids.write({
                    'location_dest_id': destination['location_id'],
                    'result_package_id': destination['package_id'],
                })
            if destination['package_id']:
                move.picking_id.return_destination_package_id = destination['package_id']

        new_picking.invalidate_recordset(['batch_id'])
        if not new_picking.batch_id:
            raise UserError(_("Customer return transfer was created but could not be assigned to the return batch."))

    def _get_returnable_qty_for_move(self, move):
        self.ensure_one()
        quantity = move.quantity
        for returned_move in move.move_dest_ids.filtered(lambda m: m.origin_returned_move_id == move):
            quantity -= returned_move.quantity
        return max(float_round(quantity, precision_rounding=move.product_id.uom_id.rounding), 0.0)

    def _get_customer_return_configuration(self):
        self.ensure_one()
        picking_type = self.company_id.mataa_return_picking_type_id
        if not picking_type:
            raise UserError(_("Miss configuration: No return operation type found"))
        inhouse_location = self.company_id.mataa_return_inhouse_location_id
        if not inhouse_location:
            raise UserError(_("Miss configuration: Default Return Inhouse Location was not found"))
        return picking_type, inhouse_location

    def action_create_dms_customer_return(self, returned_items=None):
        self.ensure_one()
        self = self.sudo()

        if self.picking_type_code != 'outgoing':
            raise UserError(_("DMS returns can only be created from outgoing pickings."))
        if self.state != 'done':
            raise UserError(_("DMS returns can only be created from done outgoing pickings."))

        self._get_customer_return_configuration()

        with self.env.cr.savepoint():
            return_wizard = self.env['stock.return.picking'].sudo().with_context(
                active_model='stock.picking',
                active_id=self.id,
                active_ids=self.ids,
            ).create({
                'picking_id': self.id,
            })
            return_wizard._compute_moves_locations()

            normalized_items = {}
            for item in returned_items or []:
                code = str(item.get('code') or '').strip()
                qty = float(item.get('returnedGoods') or 0.0)
                if not code or qty <= 0:
                    continue
                normalized_items[code.casefold()] = normalized_items.get(code.casefold(), 0.0) + qty

            if not normalized_items:
                for line in return_wizard.product_return_moves.filtered('move_id'):
                    line.quantity = self._get_returnable_qty_for_move(line.move_id)
                action = return_wizard.create_returns()
            else:
                return_wizard.product_return_moves.write({'quantity': 0.0})
                unmatched_codes = set(normalized_items)

                for code, qty_to_return in list(normalized_items.items()):
                    candidate_lines = return_wizard.product_return_moves.filtered(
                        lambda line: code in {
                            str(line.product_id.default_code or '').strip().casefold(),
                            str(line.product_id.barcode or '').strip().casefold(),
                        } or code in {str(barcode).casefold() for barcode in line.product_id.barcode_ids.mapped('name') if barcode}
                    )

                    for line in candidate_lines:
                        if qty_to_return <= 0:
                            break
                        available_qty = self._get_returnable_qty_for_move(line.move_id)
                        if available_qty <= 0:
                            continue
                        assigned_qty = min(available_qty, qty_to_return)
                        line.quantity = assigned_qty
                        qty_to_return -= assigned_qty

                    if qty_to_return > 0:
                        raise UserError(_("Returned quantity for code '%s' exceeds the remaining returnable quantity.") % code)
                    unmatched_codes.discard(code)

                if unmatched_codes:
                    raise UserError(_("Returned product code(s) not found in shipment: %s") % ', '.join(sorted(unmatched_codes)))

                action = return_wizard.create_returns()

            return_picking = self.env['stock.picking'].sudo().browse(action.get('res_id'))
            if return_picking and return_picking.state not in ('done', 'cancel'):
                return_picking.with_context(skip_dms_shipment_update=True).button_validate()

            return return_picking

    def _get_customer_return_destination(self, product, sale_line=False):
        self.ensure_one()

        return_location = self.company_id.mataa_return_location_id or self.env['stock.location'].search([
            ('complete_name', '=', 'WH/Stock/Return'),
            ('company_id', 'in', [False, self.company_id.id]),
        ], limit=1)
        if not return_location:
            raise UserError(_("Miss configuration: No return destination location found"))

        if sale_line and sale_line.vendor_id and not sale_line.inhouse_location:
            return return_location, False

        Quant = self.env['stock.quant'].sudo()
        _picking_type, inhouse_location = self._get_customer_return_configuration()

        inhouse_quants = Quant.search([
            ('product_id.product_tmpl_id', '=', product.product_tmpl_id.id),
            ('quantity', '>', 0),
            ('location_id', '=', inhouse_location.id),
            ('company_id', '=', self.company_id.id),
            ('package_id', '!=', False),
        ], order='in_date asc')

        same_variant_packaged_quant = inhouse_quants.filtered(
            lambda q: q.product_id.id == product.id
        )[:1]
        if same_variant_packaged_quant:
            return inhouse_location, same_variant_packaged_quant.package_id

        return inhouse_location, False

    def create_return_to_vendor_pickings(self, purchase_moves_by_picking):
        self.ensure_one()
        for picking_id, purchase_move_ids in purchase_moves_by_picking.items():
            picking_id = self.env['stock.picking'].browse(picking_id)
            purchase_move_ids = self.env['stock.move'].browse(purchase_move_ids)

            new_picking = picking_id.copy({
                'move_ids': [],
                'picking_type_id': picking_id.picking_type_id.return_picking_type_id.id or picking_id.picking_type_id.id,
                'state': 'draft',
                'location_id': self.company_id.mataa_return_location_id.id,
                'location_dest_id': picking_id.location_id.id,
                'partner_id': picking_id.partner_id.id,
                'return_id': picking_id.id,
                'origin': _("Return of %s -- Triggered from customer return %s", picking_id.name, self.name),
                'group_id': picking_id.group_id.id,
                'note': picking_id.partner_id.name or "",
            })
            new_picking.message_post_with_source(
                'mail.message_origin_link',
                render_values={'self': new_picking, 'origin': picking_id},
                subtype_xmlid='mail.mt_note',
            )
            for move in purchase_move_ids:
                move.copy({
                    'picking_id': new_picking.id,
                    'state': 'draft',
                    'date': fields.Datetime.now(),
                    'location_id': new_picking.location_id.id,
                    'location_dest_id': new_picking.location_dest_id.id,
                    'picking_type_id': new_picking.picking_type_id.id,
                    'warehouse_id': new_picking.picking_type_id.warehouse_id.id,
                })
            new_picking.action_confirm()

    @api.model_create_multi
    def create(self, vals):
        sp_ids = super(Picking, self).create(vals)
        if 'INT' in sp_ids[0].name and self._context.get('mataa_purchase_partner_id'):
            sp_ids.partner_id = self._context.get('mataa_purchase_partner_id')

        sale_order_ids = sp_ids.mapped('group_id.sale_id')
        sale_order_ids.update_mataa_status()
        sale_order_ids.mapped('order_line').update_line_status()

        return sp_ids

    def _get_fields_stock_barcode(self):
        res = super(Picking, self)._get_fields_stock_barcode()
        res.extend(['mataa_sale_order_id', 'mataa_tickets_count'])
        return res

    def export_move_lines(self):
        self.ensure_one()
        sml_ids = self.move_line_ids.ids
        return {
            'type': 'ir.actions.act_url',
            'url': '/export/sml/%s' % sml_ids,
            'target': 'download',
        }

    def action_print_related_so_bulk(self):
        """
        Prints the Sales Orders for the selected pickings.
        """
        sale_orders = self.mapped('sale_id')
        suspended_sale_orders = sale_orders.filtered(lambda so: so.is_suspended)
        if not sale_orders:
            raise UserError(_("None of the selected pickings are linked to a Sales Order."))
        if suspended_sale_orders:
            raise UserError(f"The following orders are suspended: {', '.join(suspended_sale_orders.mapped('name'))}. Please deselect them to print the related invoices.")


        return self.env.ref('mataa_order_management.mataa_sales_order').report_action(sale_orders)

    def action_print_related_invoices_bulk(self):
        """
        Prints the Posted Invoices for the selected pickings.
        It will ignore pickings that do not have a posted invoice.
        """
        posted_invoices = self.mapped('sale_id.invoice_ids').filtered(lambda inv: inv.state == 'posted')
        if not posted_invoices:
            raise UserError(_("No posted invoices found for the selected pickings."))

        return self.env.ref('mataa_order_management.mataa_account_invoices').report_action(posted_invoices)


    @api.depends('state')
    def _compute_total_received_value(self):
        for picking in self:
            total_value = 0.0
            origion = picking.origin
            purchase_orders = self.env['purchase.order'].search([('name', '=', origion)])
            if picking.state == 'done':
                for move in picking.move_ids:
                    if move.purchase_line_id:
                        price_unit = purchase_orders.order_line.search([('id', '=', move.purchase_line_id.id)]).price_unit
                        move_value = move.quantity * price_unit  
                        total_value += move_value
    
            picking.total_received_value = total_value

    def action_put_in_pack(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'choose.package.wizard',
            'view_mode': 'form',
            'target': 'new',
            'views': [(False, 'form')],  # Added views to prevent JS error
            'context': {
                'default_picking_id': self.id,
            },
        }
