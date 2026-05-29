import requests

from odoo import api, models
from odoo.exceptions import UserError
from ..constants.quick_sync_constants import QuickSyncConstants


class QuickService:

    @staticmethod
    def get_vendor(env, vendor_name):
        """Get vendor by name"""
        vendor = env['res.partner'].search([('name', '=', vendor_name)], limit=1)

        return vendor

    @staticmethod
    def quick_update(env, id, regular_price, sales_price, variant_id, variant_regular_price, vendor_info):
        product_template = env['product.template'].search([('id', '=', id)], limit=1)
 
        product_template.with_context(skip_vendor_price_check=True).write({
            'regular_price': regular_price or product_template.regular_price,
            'list_price': sales_price or product_template.list_price,
            'last_modified_by': 'Advanced Import (Quick)',
        })

        product_variant = env['product.product'].search([('id', '=', variant_id)], limit=1)
        product_variant.with_context(skip_vendor_price_check=True).write({
            'regular_price': variant_regular_price or product_variant.regular_price,
        })

        supplier_info = env['product.supplierinfo'].search([
            ('product_tmpl_id', '=', product_variant.product_tmpl_id.id),
            ('partner_id', '=', vendor_info['vendor'].id),
            ('product_id', '=', product_variant.id)
        ], limit=1)

        if supplier_info:
            vendor_price = vendor_info['vendor_price'] if (vendor_info['vendor_price'] != None) else supplier_info.price
            vendor_quantity = vendor_info['vendor_quantity'] if (vendor_info['vendor_quantity'] != None) else supplier_info.min_qty
            # Update existing supplier info
            supplier_info.with_context(skip_vendor_price_check=True, from_import=True).write({
                'product_name': vendor_info['vendor_product_name'] or supplier_info.product_name,
                'product_code': vendor_info['vendor_product_code'] or supplier_info.product_code,
                'price': vendor_price,
                'min_qty': vendor_info['vendor'].check_quantity(vendor_quantity)
            })
        else:
            # Create new supplier info for the vendor and variant
            env['product.supplierinfo'].with_context(skip_vendor_price_check=True, from_import=True).create({
                'partner_id': vendor_info['vendor'].id,
                'product_tmpl_id': product_variant.product_tmpl_id.id,
                'product_id': product_variant.id,
                'product_name': vendor_info['vendor_product_name'],
                'product_code': vendor_info['vendor_product_code'],
                'price': vendor_info['vendor_price'],
                'min_qty': vendor_info['vendor'].check_quantity(vendor_info['vendor_quantity'])
            })

    @staticmethod
    def quick_sync(target_data):
        url = QuickSyncConstants.get_quick_update_url()
        headers = {
            "Content-Type": "application/json"
        }

        response = requests.put(url, json=target_data, headers=headers, verify=False)

        try:
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as err:
            raise UserError(
                f"Error Quick import update {err}")
            return None