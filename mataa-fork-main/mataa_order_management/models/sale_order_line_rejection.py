from odoo import models, fields, api


class SaleOrderLineRejection(models.Model):
    _name = 'sale.order.line.rejection'
    _description = 'Sale Order Line Rejection'

    sale_order_line_id = fields.Many2one(
        'sale.order.line',
        string='Sale Order Line',
        required=True,
        ondelete='cascade'
    )
    related_sale_order_id = fields.Many2one(
        'sale.order',
        string='Related Sale Order',
        related='sale_order_line_id.order_id',
        store=True,
        readonly=True
    )
    related_customer_id = fields.Many2one(
        'res.partner',
        string='Related Customer',
        related='sale_order_line_id.order_partner_id',
        store=True,
        readonly=True
    )
    related_vendor_id = fields.Many2one(
        'res.partner',
        string='Related Vendor',
        related='sale_order_line_id.vendor_id',
        store=True,
        readonly=True
    )
    related_product_id = fields.Many2one(
        'product.product',
        string='Product',
        related='sale_order_line_id.product_id',
        store=True,
        readonly=True
    )
    related_product_default_code = fields.Char(
        string='Product Internal Reference',
        related='sale_order_line_id.product_default_code',
        store=True,
        readonly=True
    )
    related_product_brand_id = fields.Many2one(
        'product.brand',
        string='Brand',
        related='sale_order_line_id.product_brand_id',
        store=True,
        readonly=True
    )
    related_product_categ_id = fields.Many2one(
        'product.category',
        string='Category',
        related='sale_order_line_id.product_categ_id',
        store=True,
        readonly=True
    )
    rejected_qty = fields.Float(
        'Rejected Quantity',
        required=True,
        digits='Product Unit of Measure'
    )
    was_inhouse_available = fields.Boolean(
        'Was In-house Available',
        help="Indicates if there was sufficient in-house stock when the rejection occurred."
    )
    reason = fields.Text('Reason')
    rejection_date = fields.Datetime(
        'Rejection Date',
        default=fields.Datetime.now,
        readonly=True
    )
    user_id = fields.Many2one(
        'res.users',
        'Rejected By',
        default=lambda self: self.env.user,
        readonly=True
    )