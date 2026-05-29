from odoo import models, fields, api, _
from odoo.exceptions import UserError
from ..utility.import_quick_file_parser import ImportQuickFileParser
from ..services.attribute_service import AttributeService
from ..services.category_service import CategoryService
from ..services.product_service import ProductService
from ..services.tag_service import TagService
from ..services.variant_service import VariantService
from ..services.vendor_service import VendorService
from ..services.brand_service import BrandService
from ..services.quick_service import QuickService
import logging

_logger = logging.getLogger(__name__)


class ImportQuickWizard(models.TransientModel):
    _name = 'import.quick.wizard'
    _description = 'Import Quick Update'
    # TODO : Quick sync should be fixed/removed after the new catalog system
    
    import_file = fields.Binary(string="Upload File", required=True)
    file_name = fields.Char(string="File Name")

    def import_quick(self):
        """Main method for importing and processing quick"""
        if not self.import_file:
            raise UserError("No file uploaded.")

        # Parse the uploaded file
        data = ImportQuickFileParser.parse_file(self.file_name, self.import_file)

        batch_size = 50  # Define the batch size
        product_data_list = []
        skipped_variants = []  # Collect skipped variants

        # Process data in batches
        for start in range(0, len(data), batch_size):
            _logger.info(f"Processing Batch: {start} ~ {start + batch_size}")
            batch = data.iloc[start:start + batch_size]
            for idx, row in batch.iterrows():
                try:
                    _logger.info(f"# Processing Row {idx}")
                    is_skipped, product_data = self.process_row(row)
                    if is_skipped:
                        skipped_variants.append(product_data)  # Collect skipped variant information
                    elif product_data:
                        product_data_list.append(product_data)  # Collect valid variant data
                except Exception as e:
                    _logger.error(f"Failed to process row {idx + 1}: {e}")
                    raise UserError(f"Error processing row {idx + 1}:\n{e}")

        # Log start of variant update process
        _logger.info("Starting variant update process for all processed rows...")

        # Update variants after all rows are processed
        for product_data in product_data_list:
            try:
                _logger.info(f"Updating variant: {product_data['variant_id']}")
                QuickService.quick_update(
                    env=self.with_context(pre_sync=True).env,
                    id=product_data['id'],
                    regular_price=product_data['regular_price'],
                    sales_price=product_data['sales_price'],
                    variant_id=product_data['variant_id'],
                    variant_regular_price=product_data['variant_regular_price'],
                    vendor_info=product_data.get('vendor_info'),
                )
            except Exception as e:
                raise UserError(f"Error while updating : \n{product_data}\n -{e}")

            # Check vendor price with sale and regular price
            vendor_price = product_data['vendor_info']['vendor_price'] if 'vendor_price' \
                                                                          in product_data['vendor_info'] else 0
            product = self.env['product.template'].browse(product_data['id'])
            self.env['product.supplierinfo'].check_prices(product, vendor_price, product_data['sales_price'],
                                                          product_data['regular_price'])

        products_to_be_synced = []

        for item in product_data_list:
            to_be_synced_template = self.env['product.template'].browse(item['id'])

            if to_be_synced_template.mataa_id and to_be_synced_template.is_synced:
                product_regular_price = str(to_be_synced_template.regular_price) if to_be_synced_template.regular_price else to_be_synced_template.list_price
                product_sale_price = (
                    str(to_be_synced_template.list_price)) \
                    if (to_be_synced_template.list_price
                        and product_regular_price
                        and to_be_synced_template.list_price <= float(product_regular_price)) \
                    else None
                product_template_quantity = sum(
                    variant.free_qty + sum(
                        seller.min_qty for seller in variant.seller_ids if seller.product_id.id == variant.id
                    )
                    for variant in to_be_synced_template.product_variant_ids
                )
                products_to_be_synced.append({
                    "id": to_be_synced_template.mataa_id,
                    "quantity": int(product_template_quantity) if product_template_quantity else 0,
                    "price": float(product_regular_price) if product_regular_price else 0,
                    "salePrice": float(product_sale_price) if product_sale_price else 0
                })

                to_be_synced_variants = self.env['product.product'].search([
                    ('product_tmpl_id', '=', to_be_synced_template.id),
                    ('mataa_id', '!=', None),
                    ('is_synced', '=', True)
                ])

                if to_be_synced_variants:
                    for to_be_synced_variant in to_be_synced_variants:
                        variant_regular_price = str(
                            to_be_synced_variant.regular_price) if to_be_synced_variant.regular_price and to_be_synced_variant.regular_price > 0 else str(
                            to_be_synced_variant.lst_price)
                        variant_sale_price = str(to_be_synced_variant.lst_price) if to_be_synced_variant.lst_price and str(
                            to_be_synced_variant.lst_price) != variant_regular_price else None

                        supplier_list_quantity = sum(
                            seller.min_qty for seller in to_be_synced_variant.seller_ids if seller.product_id.id == to_be_synced_variant.id)
                        product_quantity = supplier_list_quantity + to_be_synced_variant.free_qty

                        products_to_be_synced.append({
                            "id": to_be_synced_variant.mataa_id,
                            "quantity": int(product_quantity) if product_quantity else 0,
                            "price": float(variant_regular_price) if variant_regular_price else 0,
                            "salePrice": float(variant_sale_price) if variant_sale_price else 0
                        })

        if len(products_to_be_synced) > 0:
            sync_batch_size = 2000
            for start in range(0, len(products_to_be_synced), sync_batch_size):
                _logger.info(f"Syncings Batch: {start} ~ {start + sync_batch_size}")
                batch = products_to_be_synced[start:start + sync_batch_size]
                QuickService.quick_sync(batch)
        # Create history line
        self.env['log.imports'].create({'file_name': self.file_name})

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
        # Template details
        template_internal_ref = row.get('template_internal_ref')
        template_regular_price = row.get('template_regular_price')
        template_sales_price = row.get('template_sales_price')

        # Variant details
        variant_internal_ref = row.get('variant_internal_ref')
        variant_regular_price = row.get('variant_regular_price')

        # Vendor details
        vendor_name = row.get('variant_vendor_name')
        vendor_product_name = row.get('variant_vendor_product_name')
        vendor_product_code = row.get('variant_vendor_product_code')
        vendor_price = row.get('variant_vendor_price')
        vendor_quantity = row.get('variant_vendor_quantity')

        existing_product = ProductService.get_product(self.env, template_internal_ref)
        if not existing_product:
            return True, template_internal_ref  # Mark as skipped if template doesn't exist

        existing_variant = VariantService.get_variant(self.env, existing_product, variant_internal_ref)
        if not existing_variant:
            return True, variant_internal_ref  # Mark as skipped if template doesn't exist

        product_data = {
            'id': existing_product.id,
            'regular_price': template_regular_price,
            'sales_price': template_sales_price,
            'variant_id': existing_variant.id,
            'variant_regular_price': variant_regular_price,
        }

        # Add vendor information if available
        if vendor_name and vendor_price is not None:
            product_vendor = VendorService.get_vendor(self.env, vendor_name)
            if not product_vendor:
                raise UserError(f"Vendor {vendor_name} does not exist.")

            product_data['vendor_info'] = {
                'vendor': product_vendor,
                'vendor_product_code': vendor_product_code,
                'vendor_product_name': vendor_product_name,
                'vendor_price': vendor_price,
                'vendor_quantity': vendor_quantity,
            }

        return False, product_data
