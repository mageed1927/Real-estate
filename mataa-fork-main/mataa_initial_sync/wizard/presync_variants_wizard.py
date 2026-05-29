from odoo import models, fields, api
from odoo.exceptions import UserError
from ..utility.variants_file_parser import VariantsFileParser
from ..services.vendor_service import VendorService
from ..services.attribute_service import AttributeService
from ..services.variant_service import VariantService
from ..services.product_service import ProductService
from ..services.brand_service import BrandService
# from odoo.addons.mataa_external_sync.services.variant_sync_service import VariantSyncService

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class PreSyncVariantsWizard(models.TransientModel):
    _name = 'presync.variants.wizard'
    _description = 'Initial Presync variants'

    import_file = fields.Binary(string="Upload File", required=True)
    file_name = fields.Char(string="File Name")

    def presync_variants(self):
        if not self.import_file:
            raise UserError("No file uploaded.")

        # Parse the uploaded file
        data = VariantsFileParser.parse_file(self.file_name, self.import_file)

        batch_size = 50  # Define the batch size
        variant_data_list = []
        skipped_variants = []  # Collect skipped variants

        # Process data in batches
        for start in range(0, len(data), batch_size):
            _logger.info(f"Processing Batch: {start} ~ {start + batch_size}")
            batch = data.iloc[start:start + batch_size]
            for idx, row in batch.iterrows():
                try:
                    _logger.info(f"# Processing Row {idx}")
                    is_skipped, variant_data = self.process_row(row)
                    if is_skipped:
                        skipped_variants.append(variant_data)  # Collect skipped variant information
                    elif variant_data:
                        variant_data_list.append(variant_data)  # Collect valid variant data
                except Exception as e:
                    _logger.error(f"Failed to process row {idx + 1}: {e}")
                    raise UserError(f"Error processing row {idx + 1}:\n{e}")

        # Log start of variant update process
        _logger.info("Starting variant update process for all processed rows...")

        # Update variants after all rows are processed
        for variant_data in variant_data_list:
            try:
                _logger.info(f"Updating variant: {variant_data['variant_name']} (Mataa ID: {variant_data['mataa_id']})")
                updated_variant = VariantService.update_product_variant(
                    env=self.with_context(pre_sync=True).env,
                    mataa_id=variant_data['mataa_id'],
                    product_template=variant_data['product_template'],
                    variant_name=variant_data['variant_name'],
                    internal_ref=variant_data['internal_ref'],
                    regular_price=variant_data['regular_price'],
                    sales_price=variant_data['sales_price'],
                    barcodes=variant_data['barcodes'],
                    attribute_values=variant_data['attribute_values'],
                )

                # Link vendor information to the variant after updating
                if variant_data.get('vendor_info'):
                    vendor_info = variant_data['vendor_info']
                    VendorService.link_vendor_to_variant(
                        self.env,
                        vendor=vendor_info['vendor'],
                        product_variant=updated_variant,
                        vendor_product_name=vendor_info['vendor_product_name'],
                        vendor_code=vendor_info['vendor_product_code'],
                        vendor_price=vendor_info['vendor_price'],
                        vendor_quantity=vendor_info['vendor_quantity']
                    )
            except Exception as e:
                raise UserError(f"Error while updating : \n{variant_data}\n -{e}")

        # Display a notification with the skipped variants if any
        if skipped_variants:
            skipped_variant_names = ", ".join(skipped_variants)
            _logger.info(f"The following variants were skipped: {skipped_variant_names}")
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _("Note: Skipped Variants (Already Exists)"),
                    'message': _("The following variants were skipped: %s") % skipped_variant_names,
                    'sticky': True,
                }
            }

    def process_row(self, row):
        mataa_id = row.get('mataa_id')
        template_mataa_id = row.get('template_mataa_id')
        default_code = row.get('default_code')
        name = row.get('name')
        regular_price = row.get('regular_price')
        sales_price = row.get('sales_price')
        barcode = row.get('barcode')
        vendor_quantity = row.get('vendor_quantity')
        vendor_name = row.get('vendor_name')
        vendor_product_code = row.get('vendor_product_code')
        vendor_product_name = row.get('vendor_product_name')
        vendor_price = row.get('vendor_price')
        attributes = row.get('attributes', [])

        # Validate WooCommerce variant existence
        # try:
        #     wc_variant = VariantSyncService.get_by_id(target_id=mataa_id, parent_id=template_mataa_id)
        #     if not wc_variant.get('id'):
        #         raise UserError(f"Variant {mataa_id} doesn't exist on WooCommerce.")
        # except Exception as e:
        #     raise UserError(f"Error in WooCommerce validation:\n{e}")

        # Validate product template existence
        existing_product = ProductService.get_product_by_mataa_id(self.env, template_mataa_id)
        if not existing_product:
            return True, name  # Mark as skipped if template doesn't exist

        # Collect attribute values
        variant_attribute_values = []
        for attribute in attributes:
            existing_attribute = AttributeService.get_attribute(env=self.env, mataa_id=attribute.get('mataa_id'))
            if not existing_attribute:
                raise UserError(f"Attribute with ID {attribute.get('mataa_id')} does not exist.")

            existing_attribute_value = AttributeService.get_attribute_value(
                env=self.env,
                attribute_mataa_id=attribute.get('mataa_id'),
                mataa_id=attribute.get('value_mataa_id')
            )
            if not existing_attribute_value:
                raise UserError(
                    f"Attribute value with ID {attribute.get('value_mataa_id')} for attribute {attribute.get('mataa_id')} does not exist."
                )

            variant_attribute_values.append(existing_attribute_value)

        # Collect data for variant update
        variant_data = {
            'mataa_id': mataa_id,
            'product_template': existing_product,
            'variant_name': name,
            'internal_ref': default_code,
            'regular_price': regular_price,
            'sales_price': sales_price,
            'barcodes': [barcode],
            'attribute_values': variant_attribute_values,
        }

        # Add vendor information if available
        if vendor_name and vendor_price is not None:
            product_vendor = VendorService.get_vendor(self.env, vendor_name)
            if not product_vendor:
                raise UserError(f"Vendor {vendor_name} does not exist.")

            variant_data['vendor_info'] = {
                'vendor': product_vendor,
                'vendor_product_code': vendor_product_code,
                'vendor_product_name': vendor_product_name,
                'vendor_price': vendor_price,
                'vendor_quantity': vendor_quantity,
            }

        return False, variant_data  # Return data for variant update if all validations pass
