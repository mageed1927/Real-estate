# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    # VMS Integration Fields
    vms_vendor_type = fields.Selection([
        ('standard', 'Standard Vendor'),
        ('in_house', 'In-House Vendor'),
    ], string='VMS Vendor Type', 
       related='partner_id.vendor_type', 
       readonly=True,
       help='VMS vendor type of the partner')
    
    vms_related_vendors = fields.Many2many(
        'res.partner',
        string='VMS Related Vendors',
        compute='_compute_vms_related_vendors',
        help='All related vendors in the VMS system'
    )
    
    vms_total_related_balance = fields.Monetary(
        string='VMS Total Related Balance',
        compute='_compute_vms_related_balance',
        store=True,
        help='Total balance across all related vendor accounts'
    )

    @api.depends('partner_id', 'partner_id.vendor_type', 'partner_id.standard_vendor_partner_id', 'partner_id.in_house_vendor_partner_ids')
    def _compute_vms_related_vendors(self):
        """Compute all related vendors in the VMS system"""
        for order in self:
            if not order.partner_id.is_vms_vendor:
                order.vms_related_vendors = False
                continue
            
            if order.partner_id.vendor_type == 'standard':
                # Standard vendor + all in-house vendors
                order.vms_related_vendors = order.partner_id + order.partner_id.in_house_vendor_partner_ids
            elif order.partner_id.vendor_type == 'in_house':
                # In-house vendor + standard vendor
                order.vms_related_vendors = order.partner_id + order.partner_id.standard_vendor_partner_id
            else:
                order.vms_related_vendors = order.partner_id

    @api.depends('vms_related_vendors')
    def _compute_vms_related_balance(self):
        """Compute total balance across all related vendors"""
        for order in self:
            if not order.vms_related_vendors:
                order.vms_total_related_balance = 0.0
                continue
            
            total_balance = 0.0
            for vendor in order.vms_related_vendors:
                total_balance += vendor.vms_total_balance or 0.0
            
            order.vms_total_related_balance = total_balance

    def get_vms_po_data(self):
        """Get comprehensive VMS PO data"""
        self.ensure_one()
        
        return {
            'id': self.id,
            'name': self.name,
            'partner_id': self.partner_id.id,
            'partner_name': self.partner_id.name,
            'vendor_type': self.vms_vendor_type,
            'date_order': self.date_order.isoformat() if self.date_order else None,
            'date_planned': self.date_planned.isoformat() if self.date_planned else None,
            'state': self.state,
            'amount_total': self.amount_total,
            'amount_untaxed': self.amount_untaxed,
            'amount_tax': self.amount_tax,
            'currency_id': self.currency_id.id,
            'currency_symbol': self.currency_id.symbol,
            'order_line': [
                {
                    'id': line.id,
                    'product_id': line.product_id.id,
                    'product_name': line.product_id.name,
                    'product_code': line.product_id.default_code,
                    'product_qty': line.product_qty,
                    'qty_received': line.qty_received,
                    'qty_invoiced': line.qty_invoiced,
                    'price_unit': line.price_unit,
                    'price_subtotal': line.price_subtotal,
                    'price_tax': line.price_tax,
                    'price_total': line.price_total,
                }
                for line in self.order_line
            ],
            'related_vendors': [
                {
                    'id': vendor.id,
                    'name': vendor.name,
                    'vendor_type': vendor.vendor_type,
                    'balance': vendor.vms_total_balance or 0.0,
                }
                for vendor in self.vms_related_vendors
            ],
            'total_related_balance': self.vms_total_related_balance,
        }

    def get_vms_po_summary(self):
        """Get VMS PO summary data"""
        self.ensure_one()
        
        return {
            'id': self.id,
            'name': self.name,
            'partner_name': self.partner_id.name,
            'date_order': self.date_order.isoformat() if self.date_order else None,
            'state': self.state,
            'amount_total': self.amount_total,
            'total_qty': sum(self.order_line.mapped('product_qty')),
            'received_qty': sum(self.order_line.mapped('qty_received')),
            'invoiced_qty': sum(self.order_line.mapped('qty_invoiced')),
        }
