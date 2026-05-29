# -*- coding: utf-8 -*-

from odoo import models, api, fields, _
from odoo.exceptions import ValidationError
from odoo import http
from odoo.http import request


class StockWarehouseOrderpoint(models.Model):
    _inherit = 'stock.warehouse.orderpoint'

    last_purchase_date = fields.Date(
        string='Last Purchase Date',
        related='product_id.last_purchase_date',
        store=True,
        readonly=True
    )

    # TOOD : verify the need for this
    # @api.depends('product_id.stock_move_ids.state', 'product_id.stock_move_ids.date')
    # def _compute_last_purchase_date(self):
    #     for orderpoint in self:
    #         last_move = self.env['stock.move'].search([
    #             ('product_id', '=', orderpoint.product_id.id),
    #             ('state', '=', 'done'),
    #             ('picking_type_id', 'in', [1, 7])
    #         ], order='date desc', limit=1)

    #         if last_move:
    #             orderpoint.last_purchase_date = last_move.date.date()
    #         else:
    #             orderpoint.last_purchase_date = Falses

    last_sale_date = fields.Date(
        string='Last Sale Date',
        related='product_id.last_sale_date',
        store=True
    )

    sold_qty = fields.Float(
        string='Sold Qty',
        related='product_id.sales_count',
        store=False,
        readonly=True,
        doc="Total quantity sold (from confirmed Sales Orders), matching the 'Sold' button on the product form."
    )

    brand_id = fields.Many2one(
        comodel_name='product.brand',
        string='Brand',
        related='product_id.product_tmpl_id.product_brand_id',
        store=True,
        readonly=True
    )

    template_id = fields.Many2one(
        comodel_name='product.template',
        string='Product',
        related='product_id.product_tmpl_id',
        store=True,
        readonly=True
    )

    snooze_manual = fields.Boolean(string="Snoozed Manually")

    product_image_url = fields.Char(
        string="Product Image",
        related='product_id.main_image',
        readonly=True
    )
    @api.model
    def create(self, vals):
        """
        Overrides create to check if the product is in the active vendor blacklist.
        """
        # product_id = vals.get('product_id')
        #
        # if product_id:
        #     # Search for an *active* record in the blacklist
        #     blacklist_rec = self.env['product.vendor.blacklist'].search([
        #         ('product_id', '=', product_id),
        #         ('active', '=', True)
        #     ], limit=1)
        #
        #     # Search for an *active* record in the blacklist
        #     if blacklist_rec:
        #         product = self.env['product.product'].browse(product_id)
        #         message = _("لا يمكن إضافة المنتج [%s] لأنه مدرج في القائمة السوداء.") % (product.display_name)
        #         raise ValidationError(message)

        # If not blacklisted, proceed as normal
        return super(StockWarehouseOrderpoint, self).create(vals)

    def action_replenish(self, *args, **kwargs):
        """
        Overrides the replenishment action to prevent ordering snoozed products.
        """
        # First, check if any of the selected records are snoozed
        snoozed_products = self.filtered(lambda o: o.snooze_manual)
        if snoozed_products:
            # If any are snoozed, return a warning and do not proceed
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('تنبيه'),
                    'message': _('لا يمكن إكمال الطلب لأن بعض المنتجات المختارة في حالة تأجيل (Snooze).'),
                    'type': 'warning',
                    'sticky': False,
                }
            }

        # If no products are snoozed, proceed with the original function, passing along any arguments
        return super(StockWarehouseOrderpoint, self).action_replenish(*args, **kwargs)
