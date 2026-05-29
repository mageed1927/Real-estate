# -*- coding: utf-8 -*-

from odoo import models, fields, api

from odoo import http
from odoo.http import request
from odoo.exceptions import ValidationError, UserError
from ..services.vms_service import VMSService

from odoo import _


class MataaPurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    sale_order_id = fields.Many2one('sale.order', string='Sale Order', readonly=True)
    sale_order_state = fields.Selection(related='sale_order_id.state', readonly=True)

    mataa_picking_ids = fields.Many2many('stock.picking', compute='_compute_mataa_picking_ids',
                                         string='Mataa Receptions', copy=False)
    mataa_tag_ids = fields.Many2many('so.tag', string='SO Tags', compute='_compute_mataa_tag_ids')
    customer_tag_ids = fields.Many2many('res.partner.category', string='Customer Tags', compute='_compute_customer_tag_ids')

    total_quantity = fields.Float(string="Total Quantity", compute="_compute_total_quantity", store=True)

    @api.depends('order_line.product_qty')
    def _compute_total_quantity(self):
        for order in self:
            order.total_quantity = sum(order.order_line.mapped('product_qty'))

    is_active = fields.Boolean(default=True, tracking=True)

    active = fields.Boolean(default=True, tracking=True)

    internal_note = fields.Text('Internal Note')

    def toggle_active(self):
        if self.filtered(lambda po: po.state != "cancel" and po.active):
            raise UserError(_("Only 'Canceled' orders can be archived"))
        return super().toggle_active()

    @api.depends('sale_order_id')
    def _compute_mataa_tag_ids(self):
        for order in self:
            order.mataa_tag_ids = order.sale_order_id.mataa_tag_ids

    @api.depends('sale_order_id')
    def _compute_customer_tag_ids(self):
        for order in self:
            order.customer_tag_ids = order.sale_order_id.partner_id.category_id

    @api.depends('order_line.move_ids.picking_id')
    def _compute_mataa_picking_ids(self):
        for order in self:
            all_moves = order.order_line.move_ids + order.order_line.move_ids.mapped('move_dest_ids')
            order.mataa_picking_ids = all_moves.mapped('picking_id')

    @api.depends('picking_ids', 'mataa_picking_ids')
    def _compute_incoming_picking_count(self):
        for order in self:
            order.incoming_picking_count = len(order.mataa_picking_ids)

    def action_view_picking(self):
        return self._get_action_view_picking(self.mataa_picking_ids)

    def action_split_rfq(self):
        for record in self:

            if not record.sale_order_id:
                continue

            lines_to_split = []
            for line in record.order_line:
                if line.product_qty > line.available_qty:
                    lines_to_split.append(line)

            if not lines_to_split:
                continue

            for line in lines_to_split:
                # Calculate the difference between ordered quantity and available quantity
                qty_diff = line.product_qty - line.available_qty

                # Reorder vendors by their sequence (lowest sequence first) and remove duplicates
                vendors = list(vendor.partner_id for vendor in
                                line.product_id.seller_ids.sudo()
                               .filtered(lambda s: s.product_id.id == line.product_id.id)
                               .sorted(key=lambda vendor: vendor.sequence))

                # Find the current vendor (the one that declined or partially accepted)
                current_vendor = record.partner_id

                if not record.company_id.vendor_support_team_id:
                    raise UserError(_("Miss configuration: No vendor support team found"))
                # Create a vendor support ticket
                ticket_data = {
                    'name': 'The vendor declined or partially accepted',
                    'description': """Hello Support Team,
                                    I have encountered that there's a RFQ line that does not fully accepted by the client.
                                    Please advise on how this can be implemented.
                                    Thank you""",

                    'mataa_customer_id': record.sale_order_id.partner_id.id,
                    'mataa_vendor_id': current_vendor.id,
                    'mataa_so_id': record.sale_order_id.id,
                    'mataa_po_id': record.id,
                    'mataa_product_id': line.product_id.id,

                    'team_id': record.company_id.vendor_support_team_id.id,
                    'company_id': record.company_id.id,
                }

                self.env['helpdesk.ticket'].sudo().create(ticket_data)

                # Get the index of the current vendor in the vendors list
                current_vendor_index = vendors.index(current_vendor) if current_vendor in vendors else -1

                # Check if the current vendor is the last in the list
                next_vendor = None
                for vendor in vendors[current_vendor_index + 1:]:  # Iterate over remaining vendors
                    seller_info = line.product_id.seller_ids.sudo().filtered(
                        lambda s: s.product_id.id == line.product_id.id and s.partner_id.id == vendor.id and s.min_qty >= qty_diff
                    )
                    if seller_info:
                        next_vendor = vendor
                        break  # Stop at the first suitable vendor

                if next_vendor:
                    seller_ids = line.product_id.seller_ids.sudo().filtered(
                        lambda s: s.product_id.id == line.product_id.id and s.partner_id.id == next_vendor.id
                    )

                    if seller_ids:
                        vendor_price = seller_ids[0].price or line.price_unit
                    else:
                        vendor_price = line.price_unit

                    # Create a new RFQ with lines that need to be split
                    new_record = record.sudo().copy({
                        'order_line': [(5, 0, 0)],  # Clear lines in the new RFQ
                        'sale_order_id': record.sale_order_id.id,
                        'origin': record.sale_order_id.name,
                        'partner_id': next_vendor.id,
                    })
                    new_line = line.sudo().copy({
                        'order_id': new_record.id,
                        'product_qty': qty_diff,
                        'available_qty': 0,
                        'product_id': line.product_id.id,
                        'price_unit': vendor_price  # Set the new price for the new vendor
                    })

                    # Reduce ordered quantity (min_qty) from supplier info
                    supplier_info = seller_ids[0]
                    supplier_info.sudo().write({
                        'min_qty': supplier_info.min_qty - new_line.product_qty
                    })

                else:
                    # TODO : review this
                    all_rfqs = self.env['purchase.order'].search(
                        [('state', '=', 'draft'), ('sale_order_id', '=', record.sale_order_id.id)])

                    total_available_qty = line.available_qty
                    for rfq in all_rfqs:
                        for rfq_line in rfq.order_line:
                            if rfq_line.product_id == line.product_id and line.available_qty > line.product_qty:
                                total_available_qty += line.available_qty - line.product_qty

                    sale_order_line = request.env['sale.order.line'].sudo().search(
                        [('product_id', '=', line.product_id.id),
                         ('order_id', '=', line.order_id.sale_order_id.id)]
                    )

                    if total_available_qty > 0:
                        sale_order_line.status = 'in_partially_available'
                    else:
                        sale_order_line.status = 'in_not_available'


                    if not record.company_id.customer_support_team_id:
                        raise UserError(_("Miss configuration: No customer support team found"))
                    # TODO : fix the problem with tickets permissions
                    # Create a support ticket
                    ticket_data = {
                        'name': 'No Vendor Set for RFQ Line',
                        'description': """Hello Support Team,
                                        I have encountered that there's a RFQ line that does not have any vendor set for available quantity.
                                        Please advise on how this can be implemented.
                                        Thank you""",

                        'mataa_customer_id': record.sale_order_id.partner_id.id,
                        'mataa_so_id': record.sale_order_id.id,
                        'mataa_po_id': record.id,
                        'mataa_product_id': line.product_id.id,

                        'team_id': record.company_id.customer_support_team_id.id,
                        'company_id': record.company_id.id,
                    }

                    self.env['helpdesk.ticket'].sudo().create(ticket_data)

    def action_confirm(self):
        for record in self:
            # TODO : review this
            # Handling the case where the default odoo button_confirm expects the order to be either in state 'draft' or 'sent'
            if record.state == 'to approve':
                record.state = 'sent'

            record.button_confirm()

    def button_confirm(self):
        return super(MataaPurchaseOrder,
                     self.with_context(mataa_purchase_partner_id=self.partner_id.id)).button_confirm()

    def _add_supplier_to_product(self):
        pass

    @api.model_create_multi
    def create(self, vals):
        purchase_order = super(MataaPurchaseOrder, self).create(vals)
        try:
            VMSService.send_order_to_vms(self.env, purchase_order, is_updated=False)
        except Exception as e:
            raise UserError(f'Can not send RFQ to external API. Error: {str(e)} ')
        return purchase_order

    @api.model
    def write(self, vals):
        result = super(MataaPurchaseOrder, self).write(vals)
        try:
            if any(field in vals for field in ['state', 'partner_id', 'order_line', 'amount_total']):
                # self is still the recordset!
                VMSService.send_order_to_vms(self.env, self, is_updated=True)
        except Exception as e:
            raise UserError(f'Can not update RFQ to external API. Error: {str(e)} ')
        return result