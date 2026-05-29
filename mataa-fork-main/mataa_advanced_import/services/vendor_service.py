from odoo import api, models
from odoo.exceptions import UserError


class VendorService:

    @staticmethod
    def get_vendor(env, vendor_name):
        """Get vendor by name"""
        vendor = env['res.partner'].sudo().search([('name', '=', vendor_name)], limit=1)

        return vendor

    @staticmethod
    def link_vendor_to_variant(env, vendor, product_variant, vendor_product_name=None, vendor_code=None, vendor_price=None, vendor_quantity=None):
        """Link a vendor to a product variant and update vendor-specific product information."""
        supplier_info = env['product.supplierinfo'].sudo().search([
            ('product_tmpl_id', '=', product_variant.product_tmpl_id.id),
            ('partner_id', '=', vendor.id),
            ('product_id', '=', product_variant.id)
        ], limit=1)

        if supplier_info:
            # Update existing supplier info
            qty = vendor_quantity if (vendor_quantity != None) else supplier_info.min_qty

            supplier_info.with_context(skip_vendor_price_check=True, from_import=True).sudo().write({
                'product_name': vendor_product_name or supplier_info.product_name,
                'product_code': vendor_code or supplier_info.product_code,
                'price': vendor_price or supplier_info.price,
                'min_qty': supplier_info.partner_id.check_quantity(qty)
            })
        elif not isinstance(vendor_quantity, int):
            env['product.supplierinfo'].sudo().create({
                'partner_id': vendor.id,
                'product_tmpl_id': product_variant.product_tmpl_id.id,
                'product_id': product_variant.id,
                'product_name': vendor_product_name,
                'product_code': vendor_code,
                'price': vendor_price
            })
        else:
            # Create new supplier info for the vendor and variant
            env['product.supplierinfo'].with_context(skip_vendor_price_check=True, from_import=True).sudo().create({
                'partner_id': vendor.id,
                'product_tmpl_id': product_variant.product_tmpl_id.id,
                'product_id': product_variant.id,
                'product_name': vendor_product_name,
                'product_code': vendor_code,
                'price': vendor_price,
                'min_qty': vendor.check_quantity(vendor_quantity),
                'currency_id': 99
            })

        return supplier_info
