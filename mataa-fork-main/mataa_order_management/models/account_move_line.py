# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    mataa_product_cost = fields.Monetary(string="Product Cost")
    mataa_product_cost_subtotal = fields.Monetary(
        string="Product Subtotal Cost",
        compute='_compute_mataa_product_cost_subtotal',
        store=True)
    po_name = fields.Char(string="PO")
    so_id = fields.Many2one('sale.order', string='SO')
    product_description_variants = fields.Char(string='Product Description')


    mataa_original_price = fields.Monetary(
        string="Mataa Original Price",
        currency_field='currency_id',
        help="Price before discount (for accounting split)"
    )
    mataa_discount_amount = fields.Monetary(
        string="Mataa Discount Amount",
        currency_field='currency_id',
        help="Discount amount to be posted to the dedicated discount account"
    )

    @api.depends('mataa_product_cost')
    def _compute_mataa_product_cost_subtotal(self):
        for line in self:
            line.mataa_product_cost_subtotal = line.mataa_product_cost * line.quantity

    def write(self, vals):
        res = super(AccountMoveLine, self).write(vals)
        if 'price_unit' in vals:
            sol_ids = self.env['sale.order.line'].search([('order_id.id', 'in', self.mapped('purchase_line_id.order_id.sale_order_id.id')),
                                                          ('product_id.id', 'in', self.mapped('product_id.id'))])
            sol_ids._compute_mataa_product_cost()
        return res

    @api.model_create_multi
    @api.returns('self', lambda value: value.id)
    def create(self, vals_list):
        aml_ids = super(AccountMoveLine, self).create(vals_list)

        # When creating Customer Invoice
        sol_ids = aml_ids.mapped('sale_line_ids')

        # When creating Vendor Bill
        pol_ids = aml_ids.mapped('purchase_line_id')
        sol_ids += self.env['sale.order.line'].search([('order_id.id', 'in', pol_ids.mapped('order_id.sale_order_id.id')),
                                                      ('product_id.id', 'in', pol_ids.mapped('product_id.id'))])
        sol_ids._compute_mataa_product_cost()
        for line in aml_ids:
            pol_id = line.purchase_line_id
            if pol_id:
                po_id = pol_id.order_id
                so_id = po_id.sale_order_id
                po_name = po_id.name if po_id else "N/A"
                line.write({
                    'po_name': po_name,
                    'so_id': so_id.id if so_id else False,
                    'product_description_variants': f"SO {so_id.name} / RFQ {po_name}",
                })
        return aml_ids

    @api.onchange('product_id', 'price_unit')
    def _onchange_price_vs_cost(self):
        for line in self:
            if not line.product_id or line.price_unit is None:
                continue

            cost_price = line.product_id.standard_price

            if line.price_unit < cost_price:
                return {
                    'warning': {
                        'title': "⚠️ السعر أقل من التكلفة",
                        'message': f"السعر المدخل ({line.price_unit}) أقل من تكلفة المنتج ({cost_price})!"
                    }
                }
