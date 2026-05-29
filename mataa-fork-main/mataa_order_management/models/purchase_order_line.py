# -*- coding: utf-8 -*-

from odoo import models, fields, api


class MataaPurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    so_line_image = fields.Char(
        string="Image",
        related="product_id.main_image",
        readonly=True
    )

    available_qty = fields.Float(string='Available Quantity')

    reason = fields.Char(string="Reason")
    available_date = fields.Date(string="Available Date")
    note = fields.Text(string="Note")

    last_purchase_date = fields.Date(
        string='Last PO Date',
        related='product_id.last_purchase_date',
        readonly=True,
    )
    package_name = fields.Char('Package name', help="Package name for receipt")

    def create_supplier_info(self):
        # don't use the odoo default since it creates supplier info
        pass

    @api.depends('product_qty', 'product_uom', 'company_id')
    def _compute_price_unit_and_date_planned_and_name(self):
        super(MataaPurchaseOrderLine, self)._compute_price_unit_and_date_planned_and_name()
        for line in self:
            if not line.product_id or line.invoice_lines or not line.company_id:
                continue
            seller_ids = line.product_id.seller_ids.filtered(lambda x: x.partner_id.id == line.partner_id.id)
            if seller_ids:
                line.price_unit = seller_ids[0].price

    def write(self, vals):
        res = super(MataaPurchaseOrderLine, self).write(vals)
        if 'price_unit' in vals:
            sol_ids = self.env['sale.order.line'].search([('order_id.id', 'in', self.mapped('order_id.sale_order_id.id')),
                                                          ('product_id.id', 'in', self.mapped('product_id.id'))])
            sol_ids._compute_mataa_product_cost()

        # Prioritize available_qty if it's being changed
        if 'available_qty' in vals:
            for line in self:
                modifiable_moves = line.move_ids.filtered(
                    lambda m: m.state not in ('done', 'cancel')
                )
                if modifiable_moves:
                    new_qty = line.available_qty
                    modifiable_moves.write({'product_uom_qty': new_qty})
        # Fallback to product_qty if available_qty was not changed
        elif 'product_qty' in vals:
            for line in self:
                modifiable_moves = line.move_ids.filtered(
                    lambda m: m.state not in ('done', 'cancel')
                )
                if modifiable_moves:
                    new_qty = line.product_qty
                    modifiable_moves.write({'product_uom_qty': new_qty})
        return res

    @api.model_create_multi
    @api.returns('self', lambda value: value.id)
    def create(self, vals_list):
        pol_ids =  super(MataaPurchaseOrderLine, self).create(vals_list)

        sol_ids = self.env['sale.order.line'].search([('order_id.id', 'in', pol_ids.mapped('order_id.sale_order_id.id')),
                                                      ('product_id.id', 'in', pol_ids.mapped('product_id.id'))])
        sol_ids._compute_mataa_product_cost()

        return pol_ids
