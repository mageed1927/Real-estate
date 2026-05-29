# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError

class ProductSupplierInfo(models.Model):
    _inherit = 'product.supplierinfo'

    published = fields.Boolean('Published', default=True)


    def write(self, vals):
        for supplierinfo_id in self:
            product, vendor = supplierinfo_id.get_infos(vals)
            if 'min_qty' in vals and vals['min_qty'] > 0:
                vals['min_qty'] = vendor.check_quantity(vals['min_qty'])
                if self.is_balcklisted(product, vendor) and not self.env.context.get('ignore_blacklist'):
                    if self.env.context.get('from_import', False):
                        vals['min_qty'] = 0
                    else:
                        raise UserError(f"This vendor ({vendor.name}) is blacklisted")

        return super(ProductSupplierInfo, self).write(vals)

    @api.model_create_multi
    def create(self, list_vals):
        for vals in list_vals:
            product, vendor = self.get_infos(vals)
            if 'min_qty' in vals and vals['min_qty'] > 0 and self.is_balcklisted(product, vendor):
                if self.env.context.get('from_import', False):
                    vals['min_qty'] = 0
                else:
                    raise UserError(f"This vendor ({vendor.name}) is blacklisted")

        return super(ProductSupplierInfo, self).create(list_vals)

    @api.model
    def is_balcklisted(self, product, vendor):
        blacklist_ids = self.env['product.vendor.blacklist'].search([
            ('product_id', '=', product.id),
            ('vendor_id', '=', vendor.id)])
        if product and vendor and blacklist_ids:
            return True
        return False

    def get_infos(self, vals):
        if 'product_id' not in vals:
            product = self.product_id
        else:
            product = self.env['product.product'].browse(vals['product_id'])
        if 'partner_id' not in vals:
            vendor = self.partner_id
        else:
            vendor = self.env['res.partner'].browse(vals['partner_id'])
        return product, vendor
