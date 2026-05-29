# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError


class ProductVendorBlacklist(models.Model):
    _name = 'product.vendor.blacklist'
    _description = 'Product Vendor Blacklist'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    active = fields.Boolean(default=True, tracking=True)

    product_id = fields.Many2one('product.product', string="Product", tracking=True)
    vendor_id = fields.Many2one('res.partner', string="Vendor", tracking=True)
    purchase_order_id = fields.Many2one('purchase.order', string="Purchase Order", tracking=True)
    sale_order_id = fields.Many2one('sale.order', string="Sale Order", tracking=True)
    reason = fields.Char(tracking=True)

    def _update_reordering_rules_snooze(self, snooze_status=False):
        """
        Helper method to find and update reordering rules.
        :param snooze_status: True to snooze, False to unsnooze.
        """
        if not self.product_id:
            return

        orderpoints = self.env['stock.warehouse.orderpoint'].search([
            ('product_id', 'in', self.product_id.ids)
        ])

        if orderpoints:
            orderpoints.write({'snooze_manual': snooze_status})

    @api.model
    def create(self, vals):
        # We create the blacklist record first
        record = super(ProductVendorBlacklist, self).create(vals)

        rfq_line = record.purchase_order_id.order_line.filtered(
            lambda line: line.product_id == record.product_id
        )
        vendor_id = record.vendor_id.id

        if not rfq_line:
            seller_ids = record.product_id.seller_ids.filtered(
                lambda s: s.product_id.id == record.product_id.id and s.partner_id.id == vendor_id and s.published
            )
            if seller_ids:
                seller_ids[0].sudo().write({
                    'min_qty': 0,
                })

        else:
            seller_ids = rfq_line.product_id.seller_ids.filtered(
                lambda s: s.product_id.id == rfq_line.product_id.id and s.partner_id.id == vendor_id and s.published
            )
            if seller_ids:
                seller_ids[0].sudo().write({
                    'min_qty': 0,
                })
        # Now we update its corresponding reordering rules
        record._update_reordering_rules_snooze(snooze_status=True)
        return record

    def write(self, vals):
        # We call super() first to execute the write operation
        res = super(ProductVendorBlacklist, self).write(vals)

        # Then we check if the 'active' field was changed
        if 'active' in vals:
            # If it was activated, snooze the rules
            if vals.get('active'):
                self._update_reordering_rules_snooze(snooze_status=True)
            # If it was archived, unsnooze the rules
            else:
                self._update_reordering_rules_snooze(snooze_status=False)

        return res

    def unlink(self):
        # Before deleting, we unsnooze the related rules
        self._update_reordering_rules_snooze(snooze_status=False)
        return super(ProductVendorBlacklist, self).unlink()