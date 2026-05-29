from odoo import api, models
from odoo.exceptions import UserError
from ..services.attribute_service import AttributeService


class VariantService:

    @staticmethod
    def get_variant(env,product_template, default_code):
        """Get a product template"""
        product_template = env['product.product'].sudo().search([
            ('default_code', '=', default_code),
            ('product_tmpl_id', '=', product_template.id)
        ], limit=1)

        return product_template

    @staticmethod
    def update_variant(env, product_template, variant_name, internal_ref, regular_price, barcodes):
        """Find or update an existing variant based on attribute values."""

        # Find the variant by its attribute combination
        variant = VariantService.get_variant(env, product_template, internal_ref)

        # If variant already exists, update it
        if variant:
            if variant.default_code != internal_ref:
                variant.default_code = internal_ref or variant.default_code

            if variant.regular_price != regular_price:
                variant.with_context(skip_vendor_price_check=True).regular_price = regular_price or variant.regular_price

            if barcodes and variant.barcode != barcodes[0]:
                variant.barcode = barcodes[0] if barcodes else variant.barcode
        else:
            # If variant does not exist, log an error or create new variant
            raise UserError("Variant could not be found based on the template & internal_ref")

        return variant

    @staticmethod
    def update_variant_with_attributes(env, product_template, variant_name, internal_ref, regular_price, barcodes,
                              attribute_values, mataa_status=None):
        """Find or update an existing variant based on attribute values."""

        # Find the variant by its attribute combination
        variant = None

        if attribute_values:
            attribute_value_ids = {attr for attr in attribute_values}

            # Identify common attributes (those with only one value in the template)
            for line in product_template.attribute_line_ids:
                if len(line.value_ids) == 1:
                    # Add common attribute's single value to attribute_value_ids if not already present
                    common_value_id = line.value_ids[0].id
                    attribute_value_ids.add(common_value_id)

            # Get all variants for the product template
            variants = env['product.product'].sudo().search([('product_tmpl_id', '=', product_template.id)])

            # Filter to find the exact match based on the set of attribute values
            for v in variants:
                variant_attribute_value_ids = set(v.product_template_attribute_value_ids.product_attribute_value_id.ids)
                if variant_attribute_value_ids == set(attribute_value_ids):
                    # Found the variant that matches all attribute values
                    variant = v
                    break
        else:
            if not product_template.attribute_line_ids:
                variant = env['product.product'].search([('product_tmpl_id', '=', product_template.id)], limit=1)

        # If variant already exists, update it
        if variant:
            if variant.default_code != internal_ref:
                variant.default_code = internal_ref or variant.default_code

            if variant.regular_price != regular_price:
                variant.with_context(skip_vendor_price_check=True).regular_price = regular_price or variant.regular_price

            if barcodes and variant.barcode != barcodes[0]:
                variant.barcode = barcodes[0] if barcodes else variant.barcode

            if mataa_status is not None and 'mataa_status' in variant._fields and variant.mataa_status != mataa_status:
                variant.mataa_status = mataa_status
        else:
            # If variant does not exist, log an error or create new variant
            raise UserError("Variant could not be found based on the attribute values.")

        return variant
