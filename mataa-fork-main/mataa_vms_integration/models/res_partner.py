# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # VMS Integration Fields
    is_vms_vendor = fields.Boolean(
        string='Is VMS Vendor',
        help='Check this box if this partner is part of the VMS system'
    )
    
    vendor_type = fields.Selection([
        ('standard', 'Standard Vendor'),
        ('in_house', 'In-House Vendor'),
    ], string='Vendor Type', help='Type of vendor in the VMS system')
    
    standard_vendor_partner_id = fields.Many2one(
        'res.partner',
        string='Standard Vendor Partner',
        help='Link to the standard vendor partner if this is an in-house vendor',
        domain="[('vendor_type', '=', 'standard'), ('is_vms_vendor', '=', True)]"
    )
    
    in_house_vendor_partner_ids = fields.One2many(
        'res.partner',
        'standard_vendor_partner_id',
        string='In-House Vendor Partners',
        help='In-house vendor partners linked to this standard vendor'
    )
    
    # VMS Balance Fields
    vms_total_balance = fields.Monetary(
        string='VMS Total Balance',
        compute='_compute_vms_balances',
        store=True,
        help='Total balance across all linked vendor accounts'
    )
    
    vms_outstanding_balance = fields.Monetary(
        string='VMS Outstanding Balance',
        compute='_compute_vms_balances',
        store=True,
        help='Outstanding balance (unpaid bills) across all linked vendor accounts'
    )
    
    vms_shipping_balance = fields.Monetary(
        string='VMS Shipping Balance',
        compute='_compute_vms_balances',
        store=True,
        help='Balance for goods in shipping across all linked vendor accounts'
    )
    
    vms_cancelled_balance = fields.Monetary(
        string='VMS Cancelled Balance',
        compute='_compute_vms_balances',
        store=True,
        help='Balance for cancelled transactions across all linked vendor accounts'
    )

    @api.constrains('vendor_type', 'standard_vendor_partner_id')
    def _check_vendor_type_consistency(self):
        """Ensure vendor type consistency"""
        for partner in self:
            if partner.vendor_type == 'in_house' and not partner.standard_vendor_partner_id:
                raise ValidationError(_('In-house vendors must be linked to a standard vendor partner.'))
            
            if partner.vendor_type == 'standard' and partner.standard_vendor_partner_id:
                raise ValidationError(_('Standard vendors cannot be linked to another standard vendor.'))
            
            if partner.vendor_type == 'in_house' and partner.standard_vendor_partner_id.vendor_type != 'standard':
                raise ValidationError(_('In-house vendors can only be linked to standard vendors.'))

    @api.depends('vendor_type', 'standard_vendor_partner_id', 'in_house_vendor_partner_ids')
    def _compute_vms_balances(self):
        """Compute VMS balances for the vendor"""
        for partner in self:
            if not partner.is_vms_vendor:
                partner.vms_total_balance = 0.0
                partner.vms_outstanding_balance = 0.0
                partner.vms_shipping_balance = 0.0
                partner.vms_cancelled_balance = 0.0
                continue
            
            # Get all related vendor partners
            vendor_partners = self._get_related_vendor_partners(partner)
            
            # Calculate balances
            partner.vms_total_balance = self._calculate_total_balance(vendor_partners)
            partner.vms_outstanding_balance = self._calculate_outstanding_balance(vendor_partners)
            partner.vms_shipping_balance = self._calculate_shipping_balance(vendor_partners)
            partner.vms_cancelled_balance = self._calculate_cancelled_balance(vendor_partners)

    def _get_related_vendor_partners(self, partner):
        """Get all vendor partners related to the given partner"""
        if partner.vendor_type == 'standard':
            # Return standard vendor + all in-house vendors
            return partner + partner.in_house_vendor_partner_ids
        elif partner.vendor_type == 'in_house':
            # Return in-house vendor + standard vendor
            return partner + partner.standard_vendor_partner_id
        else:
            return partner

    def _calculate_total_balance(self, vendor_partners):
        """Calculate total balance across vendor partners"""
        total = 0.0
        for vendor in vendor_partners:
            # Calculate based on account moves
            moves = self.env['account.move'].search([
                ('partner_id', '=', vendor.id),
                ('move_type', 'in', ['in_invoice', 'in_refund', 'entry']),
                ('state', '=', 'posted')
            ])
            total += sum(moves.mapped('amount_total_signed'))
        return total

    def _calculate_outstanding_balance(self, vendor_partners):
        """Calculate outstanding balance (unpaid bills) across vendor partners"""
        total = 0.0
        for vendor in vendor_partners:
            # Calculate based on unpaid bills
            moves = self.env['account.move'].search([
                ('partner_id', '=', vendor.id),
                ('move_type', 'in', ['in_invoice', 'in_refund']),
                ('state', '=', 'posted'),
                ('payment_state', '!=', 'paid')
            ])
            total += sum(moves.mapped('amount_residual'))
        return total

    def _calculate_shipping_balance(self, vendor_partners):
        """Calculate shipping balance across vendor partners"""
        total = 0.0
        for vendor in vendor_partners:
            # Calculate based on stock moves in shipping
            stock_moves = self.env['stock.move'].search([
                ('purchase_line_id.order_id.partner_id', '=', vendor.id),
                ('picking_id.picking_type_code', '=', 'incoming'),
                ('state', 'in', ['assigned', 'partially_available'])
            ])
            for stock_move in stock_moves:
                total += stock_move.product_uom_qty * stock_move.purchase_line_id.price_unit
        return total

    def _calculate_cancelled_balance(self, vendor_partners):
        """Calculate cancelled balance across vendor partners"""
        total = 0.0
        for vendor in vendor_partners:
            # Calculate based on cancelled moves
            moves = self.env['account.move'].search([
                ('partner_id', '=', vendor.id),
                ('state', '=', 'cancel')
            ])
            total += sum(moves.mapped('amount_total_signed'))
        return total

    def get_vms_vendor_data(self):
        """Get comprehensive VMS vendor data"""
        self.ensure_one()
        if not self.is_vms_vendor:
            return {}
        
        return {
            'id': self.id,
            'name': self.name,
            'vendor_type': self.vendor_type,
            'standard_vendor_id': self.standard_vendor_partner_id.id if self.standard_vendor_partner_id else None,
            'in_house_vendor_ids': self.in_house_vendor_partner_ids.ids if self.vendor_type == 'standard' else [],
            'balances': {
                'total': self.vms_total_balance,
                'outstanding': self.vms_outstanding_balance,
                'shipping': self.vms_shipping_balance,
                'cancelled': self.vms_cancelled_balance,
            },
            'contact_info': {
                'email': self.email,
                'phone': self.phone,
                'mobile': self.mobile,
                'street': self.street,
                'city': self.city,
                'country_id': self.country_id.id if self.country_id else None,
            }
        }

    @api.model
    def get_vms_vendor_by_auth(self, user_id):
        """Get VMS vendor data for authenticated user"""
        user = self.env['res.users'].browse(user_id)
        if not user.exists():
            return None
        
        # Find vendor partner linked to the user
        vendor_partner = self.search([
            ('is_vms_vendor', '=', True),
            '|',
            ('id', '=', user.partner_id.id),
            ('standard_vendor_partner_id', '=', user.partner_id.id)
        ], limit=1)
        
        if vendor_partner:
            return vendor_partner.get_vms_vendor_data()
        return None
