from odoo import api, models
from odoo.exceptions import UserError


class VendorService:

    @staticmethod
    def get_vendor(env, vendor_name):
        """Get vendor by name"""
        vendor = env['res.partner'].search([('name', '=', vendor_name)], limit=1)

        return vendor

    @staticmethod
    def create_vendor(env, mataa_id, vendor_name, vendor_email, vendor_address):
        """Get vendor by name"""
        vendor = env['res.partner'].create({
            'mataa_id': mataa_id,
            'name': vendor_name,
            'email': vendor_email,
            'street': vendor_address,
            'is_company': True,
            'supplier_rank': 1,
        })

        return vendor

    @staticmethod
    def link_vendor_to_variant(env, vendor, product_variant, vendor_product_name=None, vendor_code=None,
                               vendor_price=None, vendor_quantity=0):
        """Link a vendor to a product variant and update vendor-specific product information."""
        supplier_info = env['product.supplierinfo'].search([
            ('product_tmpl_id', '=', product_variant.product_tmpl_id.id),
            ('partner_id', '=', vendor.id),
            ('product_id', '=', product_variant.id)
        ], limit=1)

        if supplier_info:
            # Update existing supplier info
            supplier_info.write({
                'product_name': vendor_product_name or supplier_info.product_name,
                'product_code': vendor_code or supplier_info.product_code,
                'price': vendor_price or supplier_info.price,
                'min_qty': vendor_quantity or supplier_info.min_qty
            })
        else:
            # Create new supplier info for the vendor and variant
            env['product.supplierinfo'].create({
                'partner_id': vendor.id,
                'product_tmpl_id': product_variant.product_tmpl_id.id,
                'product_id': product_variant.id,
                'product_name': vendor_product_name,
                'product_code': vendor_code,
                'price': vendor_price,
                'min_qty': vendor_quantity
            })

        return supplier_info
