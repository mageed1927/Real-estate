# -*- coding: utf-8 -*-
from odoo import models, api, fields


class ExternalSync(models.Model):
    _name = 'external.sync'
    _description = 'Service for External Data Synchronization'

    def sync_ems_product_by_sku(self, data):
        t_ref = data.get('template_internal_ref')
        if not t_ref:
            return {'status': 'error', 'message': 'template_internal_ref is required'}

        # Find the Template (Main Product)
        template = self.env['product.template'].sudo().search([('default_code', '=', t_ref)], limit=1)
        if not template:
            return {'status': 'error', 'message': f'Template SKU {t_ref} not found'}

        errors = []

        # 1. Update Template Fields (Prices, Name, Brand)
        try:
            t_vals = {}
            if 'template_name' in data: t_vals['name'] = data['template_name']
            if 'template_regular_price' in data: t_vals['list_price'] = data['template_regular_price']
            if 'template_Description' in data: t_vals['description_sale'] = data['template_Description']

            # Brand Mapping
            if 'template_brand' in data and hasattr(template, 'brand_id'):
                brand = self.env['product.brand'].sudo().search([('name', '=', data['template_brand'])], limit=1)
                if brand:
                    t_vals['brand_id'] = brand.id

            if t_vals:
                template.write(t_vals)
        except Exception as e:
            errors.append(f"Template Update Error: {str(e)}")

        # 2. Update Variants (SKU, Barcode)
        variants_updated = []
        for v_data in data.get('variants', []):
            v_ref = v_data.get('variant_internal_ref')
            if not v_ref: continue

            try:
                variant = self.env['product.product'].sudo().search([
                    ('default_code', '=', v_ref),
                    ('product_tmpl_id', '=', template.id)
                ], limit=1)

                if variant:
                    v_vals = {}
                    if 'variant_name' in v_data: v_vals['name'] = v_data['variant_name']

                    # --- Barcode Safety Check ---
                    barcode = v_data.get('variant_barcodes')
                    if barcode:
                        existing = self.env['product.product'].sudo().search([
                            ('barcode', '=', barcode),
                            ('id', '!=', variant.id)
                        ], limit=1)
                        if existing:
                            errors.append(f"Barcode {barcode} skipped: Already used by {existing.default_code}")
                        else:
                            v_vals['barcode'] = barcode
                    # -----------------------------

                    if v_vals:
                        variant.write(v_vals)
                    variants_updated.append(v_ref)
                else:
                    errors.append(f"Variant SKU {v_ref} not found under Template {t_ref}")
            except Exception as e:
                errors.append(f"Variant {v_ref} Error: {str(e)}")

        return {
            'status': 'success',
            'message': 'Sync process finished',
            'updated_variants': variants_updated,
            'errors': errors
        }