# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import io
import xlsxwriter


class ProductProduct(models.Model):
    _inherit = 'product.product'

    offer_tag_ids = fields.Many2many(
        related="product_tmpl_id.offer_tag_ids",
        readonly=True,
        string="Offer Tags",
    )

    default_code = fields.Char('Internal Reference', index=True, compute=False, store=True, inverse=False)
    regular_price = fields.Float(
        string="Regular Price",
        compute='_compute_regular_price',
        inverse='_set_regular_price',
        digits='Regular Price',
        group_operator='max',
        store=True,
        tracking=True,
    )
    lst_price = fields.Float(group_operator='max')
    standard_price = fields.Float(group_operator='max')

    barcode = fields.Char(tracking=True)

    @api.depends('product_tmpl_id.regular_price')
    def _compute_regular_price(self):
        for product in self:
            product.regular_price = product.product_tmpl_id.regular_price

    def _set_regular_price(self):
        for product in self:
            if product.product_tmpl_id:
                product.product_tmpl_id.regular_price = product.regular_price
    variant_image_url_ids = fields.One2many(string="Images", comodel_name="product.url", inverse_name="product_id",
                                            ondelete='cascade')

    is_price_manager = fields.Boolean(compute='_compute_is_price_manager')

    def _compute_is_price_manager(self):
        for record in self:
            record.is_price_manager = self.env.user.has_group('__custom__.group_sales_change_prices')

    @api.constrains('default_code')
    def _check_unique_default_code(self):
        for record in self:
            if not record.default_code:
                continue
            # Search for other products with the same default_code
            existing_product = self.search([('default_code', '=ilike', record.default_code), ('id', '!=', record.id)])

            # Check templates, excluding the parent template
            duplicate_template = self.env['product.template'].search([('default_code', '=ilike', record.default_code), ('id', '!=', record.product_tmpl_id.id),], limit=1)

            # Ignore template if it owns this variant
            if duplicate_template and duplicate_template.product_variant_id.id == record.id:
                duplicate_template = False

            if existing_product or duplicate_template:
                used_by = (
                    existing_product.display_name
                    if existing_product
                    else duplicate_template.display_name
                )

                raise UserError(_(
                    "The internal reference '%s' is already used by '%s'."
                ) % (record.default_code, used_by))


    @api.constrains('regular_price', 'lst_price')
    def _check_regular_vs_lst_price(self):
        for record in self:
            if record.lst_price:
                if record.regular_price < record.lst_price:
                    raise UserError("Regular price must be larger than sale price.")

    def write(self, vals):

        return super(ProductProduct, self).write(vals)

    @api.model
    def create(self, vals):

        return super(ProductProduct, self).create(vals)

    def _get_fields_stock_barcode(self):
        return super()._get_fields_stock_barcode() + ['main_image']

    @api.constrains('regular_price', 'lst_price')
    def _check_vendor_vs_regular_vs_sale_price(self):
        for record in self:
            vendor_infos = self.env['product.supplierinfo'].search([('product_id', '=', record.id)])
            if self.env.context.get('skip_vendor_price_check', False):
                return
            self._validate_vendor_prices(vendor_infos, record)

    def _validate_vendor_prices(self, vendor_infos, product):
        prices_control = self.env['ir.config_parameter'].sudo().get_param('mataa_order_management.prices_control')
        for vendor_info in vendor_infos:
            vendor_price = vendor_info._get_converted_price(vendor_info)
            if bool(prices_control) and vendor_price > min(product.lst_price, product.regular_price):
                vendor_info._raise_invalid_price_error(vendor_info, product, vendor_price)

    def _change_standard_price(self, new_price):
        if self._context.get('skip_svl_creation'):
            return
        return super(ProductProduct, self)._change_standard_price(new_price)
