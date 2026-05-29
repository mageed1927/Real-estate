# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    # VMS Integration Fields
    vms_clearance_created = fields.Boolean(
        string='VMS Clearance Created',
        default=False,
        copy=False,
        help='Indicates if VMS clearance entry has been created'
    )
    
    vms_clearance_move_id = fields.Many2one(
        'account.move',
        string='VMS Clearance Journal Entry',
        copy=False,
        help='Journal entry created for VMS clearance'
    )
    
    vms_bill_ids = fields.Many2many(
        'account.move',
        'sale_order_account_move_rel',
        'sale_order_id',
        'account_move_id',
        string='VMS Vendor Bills',
        copy=False,
        help='Vendor bills created for this sale order'
    )

    def finalize_mataa_order(self):
        """
        Override to add VMS automations for vendor bill creation and in-house clearance.
        This is the main trigger point when an order is closed from the UI.
        """
        res = super(SaleOrder, self).finalize_mataa_order()

        for order in self:
            _logger.info(f"Starting VMS automations for finalized order {order.name}.")

            # --- VMS In-House Clearance Automation ---
            if self.env['ir.config_parameter'].sudo().get_param('mataa_vms_integration.vms_auto_clearance'):
                _logger.info(f"VMS auto-clearance is enabled. Attempting for order {order.name}.")
                order._create_inhouse_clearance_journal_entry()

            # --- VMS Vendor Bill Creation Automation ---
            if self.env['ir.config_parameter'].sudo().get_param('mataa_vms_integration.vms_auto_bill_creation'):
                _logger.info(f"VMS auto-bill creation is enabled. Attempting for order {order.name}.")
                order._create_vendor_bills_for_so()

        return res

    def _create_inhouse_clearance_journal_entry(self):
        """
        Creates a journal entry to move liability from the In-House Vendor's
        special payable account to the Standard Vendor's regular payable account.
        This process is now idempotent and checks the `vms_clearance_created` flag.
        """
        self.ensure_one()
        if self.vms_clearance_created:
            _logger.info(f"VMS clearance entry already exists for order {self.name}. Skipping.")
            return

        clearance_journal_id = self.env['ir.config_parameter'].sudo().get_param('mataa_vms_integration.vendor_clearance_journal_id')
        if not clearance_journal_id:
            _logger.warning('VMS clearance journal not configured. Skipping clearance.')
            return
        clearance_journal = self.env['account.journal'].browse(int(clearance_journal_id))

        inhouse_payable_account = self.company_id.property_account_payable_inhouse_id
        if not inhouse_payable_account:
            _logger.warning(f"VMS In-house Payable Account not configured for company {self.company_id.name}. Skipping clearance.")
            return

        vendor_lines = {}
        for line in self.order_line.filtered(lambda l: not l.display_type):
            in_house_vendor = line.product_id.seller_ids.filtered(
                lambda s: s.partner_id.is_vms_vendor and s.partner_id.vendor_type == 'in_house'
            ).mapped('partner_id')[:1]

            if in_house_vendor:
                if in_house_vendor not in vendor_lines:
                    vendor_lines[in_house_vendor] = self.env['sale.order.line']
                vendor_lines[in_house_vendor] |= line

        if not vendor_lines:
            _logger.info(f"No in-house vendor lines found for order {self.name}. No clearance entry needed.")
            return

        moves_created = self.env['account.move']
        for vendor, lines in vendor_lines.items():
            standard_partner = vendor.standard_vendor_partner_id
            if not standard_partner:
                _logger.warning(f"In-house vendor {vendor.name} is not linked to a standard vendor. Skipping clearance.")
                continue

            total_cost = 0
            for line in lines:
                delivered_qty = 0
                # Filter for moves that are done, not linked to a PO, and originate from an internal location.
                inhouse_moves = line.move_ids.filtered(
                    lambda m: m.state == 'done' and not m.purchase_line_id and m.location_id.usage == 'internal'
                )
                for move in inhouse_moves:
                    delivered_qty += move.product_uom._compute_quantity(
                        move.quantity, line.product_uom, rounding_method='HALF-UP'
                    )

                newly_purchased_qty = sum(self.env['purchase.order.line'].search([
                    ('product_id', '=', line.product_id.id),
                    ('order_id.sale_order_id', '=', line.order_id.id)]).mapped('qty_received'))

                inhouse_qty_delivered = delivered_qty - newly_purchased_qty

                total_cost += line.product_id.standard_price * inhouse_qty_delivered
            if total_cost <= 0:
                continue

            credit_account = standard_partner.property_account_payable_id

            move_vals = {
                'journal_id': clearance_journal.id,
                'date': fields.Date.today(),
                'ref': f'VMS Clearance - {self.name} - {vendor.name}',
                'move_type': 'entry',
                'line_ids': [
                    (0, 0, {
                        'name': f'Clearance for {self.name}', 'partner_id': vendor.id,
                        'account_id': inhouse_payable_account.id, 'debit': total_cost, 'credit': 0,
                    }),
                    (0, 0, {
                        'name': f'Payable for {self.name}', 'partner_id': standard_partner.id,
                        'account_id': credit_account.id, 'debit': 0, 'credit': total_cost,
                    }),
                ]
            }
            move = self.env['account.move'].create(move_vals)
            move.action_post()
            moves_created |= move

        if moves_created:
            self.write({
                'vms_clearance_created': True,
                'vms_clearance_move_id': moves_created[0].id
            })
            _logger.info(f'{len(moves_created)} VMS clearance entries created for order {self.name}')

    def _create_vendor_bills_for_so(self):
        self.ensure_one()
        all_related_pos = self._find_related_pos_for_so()
        if not all_related_pos:
            _logger.info(f"No related POs found for SO {self.name}. Skipping bill creation.")
            return

        bills_created = self.env['account.move']
        for po in all_related_pos:
            bill = self._create_or_update_vendor_bill_from_po(po)
            if bill:
                bills_created |= bill
        
        if bills_created:
            self.vms_bill_ids |= bills_created
            _logger.info(f"{len(bills_created)} vendor bills created/updated for SO {self.name}.")

    def _find_related_pos_for_so(self):
        self.ensure_one()
        
        standard_pos = self.env['purchase.order'].search([
            ('sale_order_id', '=', self.id),
            ('state', 'in', ['purchase', 'done']),
            ('partner_id.vendor_type', '=', 'standard')
        ])
        
        # TODO : remove this part of code as it was commented out on purpose as the inhouse po's have already been cleared
        # in_house_pos = self.env['purchase.order']
        # in_house_products = self.order_line.filtered(
        #     lambda l: l.product_id.seller_ids.filtered(lambda s: s.partner_id.vendor_type == 'in_house')
        # ).mapped('product_id')

        # if in_house_products:
        #     in_house_vendors = in_house_products.seller_ids.filtered(lambda s: s.partner_id.vendor_type == 'in_house').mapped('partner_id')
        #     in_house_pos = self.env['purchase.order'].search([
        #         ('partner_id', 'in', in_house_vendors.ids),
        #         ('product_id', 'in', in_house_products.ids),
        #         ('state', 'in', ['purchase', 'done']),
        #         ('invoice_status', '!=', 'invoiced')
        #     ])

        # return standard_pos | in_house_pos
        return standard_pos

    def _create_or_update_vendor_bill_from_po(self, purchase_order):
        """
        Creates a vendor bill for a PO for any newly received quantities.
        It compares qty_received to qty_invoiced on each line.
        It also checks for existing draft bills to prevent duplicates.
        This makes the process idempotent.
        """
        # First, check for any existing draft bills for this PO.
        existing_draft_bill = self.env['account.move'].search([
            ('line_ids.purchase_line_id.order_id', '=', purchase_order.id),
            ('move_type', '=', 'in_invoice'),
            ('state', '=', 'draft')
        ], limit=1)

        if existing_draft_bill:
            _logger.warning(f"PO {purchase_order.name} has an existing draft bill ({existing_draft_bill.name}). Skipping automatic bill creation to avoid duplicates. Please review manually.")
            return False

        billable_lines_data = []
        for line in purchase_order.order_line:
            # Check if there is a quantity that has been received but not yet invoiced
            qty_to_invoice = line.qty_received - line.qty_invoiced
            if qty_to_invoice > 0:
                billable_lines_data.append((0, 0, {
                    'purchase_line_id': line.id,
                    'product_id': line.product_id.id,
                    'name': line.name,
                    'quantity': qty_to_invoice,
                    'price_unit': line.price_unit,
                    'tax_ids': [(6, 0, line.taxes_id.ids)],
                }))

        if not billable_lines_data:
            _logger.info(f"No new quantities to bill for PO {purchase_order.name}. Skipping.")
            return False

        try:
            bill_vals = {
                'partner_id': purchase_order.partner_id.id,
                'purchase_id': purchase_order.id,
                'move_type': 'in_invoice',
                'ref': f'VMS Bill - {purchase_order.name}',
                'invoice_date': fields.Date.today(),
                'invoice_line_ids': billable_lines_data,
                'invoice_origin': purchase_order.name,
            }
            
            bill = self.env['account.move'].create(bill_vals)
            bill.action_post()
            _logger.info(f"Created and posted vendor bill {bill.name} for PO {purchase_order.name}.")
            return bill
            
        except Exception as e:
            _logger.error(f"Error creating vendor bill from PO {purchase_order.name}: {str(e)}")
            return False

    def action_view_vms_clearance(self):
        self.ensure_one()
        if not self.vms_clearance_move_id:
            return {'type': 'ir.actions.act_window_close'}
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('VMS Clearance Entry'),
            'res_model': 'account.move',
            'res_id': self.vms_clearance_move_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_view_vms_bills(self):
        self.ensure_one()
        if not self.vms_bill_ids:
            return {'type': 'ir.actions.act_window_close'}
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('VMS Vendor Bills'),
            'res_model': 'account.move',
            'domain': [('id', 'in', self.vms_bill_ids.ids)],
            'view_mode': 'tree,form',
            'target': 'current',
        }
