# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import logging
import datetime

_logger = logging.getLogger(__name__)

class StockPickingBatch(models.Model):
    _inherit = "stock.picking.batch"

    blanket_order_id = fields.Many2one('purchase.requisition', string='Blanket Order', readonly=False, copy=False, tracking=True)
    vendor_id = fields.Many2one('res.partner', string='Vendor', readonly=False, copy=False, tracking=True)
    carrier_id = fields.Many2one('delivery.carrier', string="Shipping Method", copy=False)
    is_customer_return_batch = fields.Boolean(string='Customer Return Batch', copy=False, readonly=True)
    return_batch_state = fields.Selection(
        [('open', 'Open'), ('verified', 'Verified')],
        string='Return Batch Status',
        default='open',
        copy=False,
        readonly=True,
        tracking=True,
    )

    @api.model
    def get_or_create_open_return_batch(self, picking_type):
        batch = self.search([
            ('is_customer_return_batch', '=', True),
            ('return_batch_state', '=', 'open'),
            ('state', 'not in', ['done', 'cancel']),
            ('picking_type_id', '=', picking_type.id),
        ], limit=1)

        if batch:
            return batch

        return self.create({
            'picking_type_id': picking_type.id,
            'is_customer_return_batch': True,
            'return_batch_state': 'open',
            'scheduled_date': datetime.datetime.now(),
        })

    def action_verify_return_batch(self):
        for batch in self:
            if not batch.is_customer_return_batch:
                continue
            if batch.return_batch_state != 'open':
                continue
            if not batch.picking_ids:
                raise UserError(_("You cannot verify an empty customer return batch."))
            batch.return_batch_state = 'verified'
        return True

    def action_client_action(self):
        self.ensure_one()
        if self.is_customer_return_batch and self.return_batch_state != 'verified':
            raise UserError(_("Verify the customer return batch before opening it in Barcode."))
        return super().action_client_action()

    def write(self, vals):
        if vals.get('picking_ids'):
            locked_batches = self.filtered(
                lambda batch: batch.is_customer_return_batch and batch.return_batch_state != 'open'
            )
            if locked_batches:
                raise UserError(_("You cannot add or remove pickings after the customer return batch is verified."))
        return super().write(vals)

    def action_done(self):
        for batch in self:
            if batch.is_customer_return_batch and batch.return_batch_state != 'verified':
                raise UserError(_("Verify the customer return batch before validating it."))

        if self.filtered('is_customer_return_batch'):
            return super(StockPickingBatch, self.with_context(skip_dms_shipment_update=True)).action_done()

        res = super(StockPickingBatch, self).action_done()

        if self.picking_type_id.id == 1: # this is the record id for 'Receipts'
            pickings_to_be_batched = set()
            picking_type_id = 5  # this is the record id for 'Internal Transfers'
            for picking in self.picking_ids:
                unique_stock_pickings = self.env['stock.picking'].sudo().search([
                    ('group_id', '=', picking.group_id.id),
                    ('picking_type_id', '=', picking_type_id)
                ])

                for p in unique_stock_pickings:
                    pickings_to_be_batched.add(p)

            batch_vals = {
                'picking_type_id': picking_type_id,
                'picking_ids': [(6, 0, [up.id for up in pickings_to_be_batched])],
                'scheduled_date': datetime.datetime.now(),
            }
            self.env['stock.picking.batch'].sudo().create(batch_vals)

        return res

    @api.model
    def _get_fields_stock_barcode(self):
        return super()._get_fields_stock_barcode() + [
            'is_customer_return_batch',
        ]

    def action_print_batch_products(self):
        self.ensure_one()

        move_lines = self.picking_ids.mapped('move_line_ids')
        if not move_lines:
            raise UserError(_("No operation lines found in this batch."))

        data = []
        for line in move_lines:
            purchase_order = (
                line.move_id.purchase_line_id.order_id
                if line.move_id.purchase_line_id
                else False
            )

            vendor_bill_ref = ""
            vendor_bill_ref_number=""
            purchase_line = line.move_id.purchase_line_id
            if purchase_line:
                invoice_lines = purchase_line.invoice_lines.filtered(
                    lambda l: l.move_id.move_type == 'in_invoice'
                              and l.move_id.state in ('draft', 'posted')
                )
                bills = invoice_lines.mapped('move_id')
                if bills:
                    vendor_bill_ref_number = ", ".join(bills.mapped('name'))
                    vendor_bill_ref = ", ".join(filter(None, bills.mapped('ref')))
            qty = line.qty_done
            if not qty:
                qty = getattr(line, "reserved_uom_qty", 0.0) or line.move_id.product_uom_qty

            uom_name = line.product_uom_id.name or line.move_id.product_uom.name
            data.append({
                'product_name': line.product_id.display_name,
                'product_code': line.product_id.default_code or '',
                'quantity': qty,
                'uom': uom_name,
                'picking_name': line.picking_id.name,
                'source': line.location_id.display_name,
                'destination': line.location_dest_id.display_name,
                'vendor_bill_name': vendor_bill_ref_number or '-',
                'vendor_bill_ref': vendor_bill_ref or '-',
            })
        _logger.info("Batch IDs being printed: %s", self.ids)
        return self.env.ref('mataa_order_management.action_report_batch_products').report_action(
            self, data={'lines': data}
        )
