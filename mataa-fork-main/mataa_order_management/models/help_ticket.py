# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError

class HelpdeskTicket(models.Model):
    _inherit = 'helpdesk.ticket'

    mataa_customer_id = fields.Many2one('res.partner', string='Related Customer', readonly=False, copy=False, tracking=True)
    mataa_vendor_id = fields.Many2one('res.partner', string='Related Vendor', readonly=False, copy=False, tracking=True)
    mataa_so_id = fields.Many2one('sale.order', string='Related Sale Order', readonly=False, copy=False, tracking=True)
    mataa_po_id = fields.Many2one('purchase.order', string='Related Purchase Order', readonly=False, copy=False, tracking=True)
    mataa_product_id = fields.Many2one('product.product', string='Related Product', readonly=False, copy=False, tracking=True)

