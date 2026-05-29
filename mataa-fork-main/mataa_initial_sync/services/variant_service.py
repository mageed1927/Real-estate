from odoo import api, models
from odoo.exceptions import UserError
from ..services.attribute_service import AttributeService


class VariantService:

    @staticmethod
    def update_product_variant(env, mataa_id, product_template, variant_name, internal_ref, regular_price, sales_price,
                               barcodes, attribute_values):
        """Find or update an existing variant based on attribute values."""

        # Find the variant by its attribute combination
        variant = None

        if not attribute_values:
            raise UserError("all variants should have attributes")

        attribute_value_ids = {attr.id for attr in attribute_values}

        # Identify common attributes (those with only one value in the template)
        for line in product_template.attribute_line_ids:
            if len(line.value_ids) == 1:
                # Add common attribute's single value to attribute_value_ids if not already present
                common_value_id = line.value_ids[0].id
                attribute_value_ids.add(common_value_id)

        # Get all variants for the product template
        variants = env['product.product'].search([('product_tmpl_id', '=', product_template.id)])

        # Filter to find the exact match based on the set of attribute values
        for v in variants:
            variant_attribute_value_ids = set(v.product_template_attribute_value_ids.product_attribute_value_id.ids)
            if variant_attribute_value_ids == set(attribute_value_ids):
                # Found the variant that matches all attribute values
                variant = v
                break

        if not product_template.regular_price or product_template.regular_price <= 1:
            if regular_price:
                product_template.with_context(pre_sync=True).write({'regular_price': regular_price})

        if not product_template.list_price or product_template.list_price <= 1:
            if not sales_price:
                sales_price = product_template.regular_price or 1
            product_template.with_context(pre_sync=True).write({'list_price': sales_price})

        # If variant already exists, update it
        if variant:
            if variant.default_code != internal_ref:
                variant.default_code = internal_ref or variant.default_code

            if variant.regular_price != regular_price:
                if regular_price > variant.lst_price or regular_price > product_template.list_price:
                    variant.regular_price = regular_price or variant.regular_price

            # if variant.lst_price != sales_price:
            #     variant.lst_price = sales_price or variant.lst_price

            if variant.barcode != barcodes[0]:
                variant.barcode = barcodes[0] if barcodes else variant.barcode
        else:
            # If variant does not exist, log an error or create new variant
            raise UserError("Variant could not be found based on the attribute values.")

        variant.write({
            'mataa_id': mataa_id,
            'is_synced': True,
            'mataa_status': 'publish'
        })

        return variant
