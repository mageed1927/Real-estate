from concurrent.futures import ThreadPoolExecutor

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from ..utility.products_file_parser import ProductsFileParser
from ..services.category_service import CategoryService
from ..services.attribute_service import AttributeService
from ..services.product_service import ProductService
from ..services.brand_service import BrandService
from ..services.vendor_service import VendorService
from ..constants.category_constants import ALLOWED_FUCNTIONAL_CATEGORY_IDS

import logging

_logger = logging.getLogger(__name__)


class PreSyncProductsWizard(models.TransientModel):
    _name = 'presync.products.wizard'
    _description = 'Initial Presync products'

    import_file = fields.Binary(string="Upload File", required=True)
    file_name = fields.Char(string="File Name")

    def presync_products(self):
        if not self.import_file:
            raise UserError("No file uploaded.")

        # Parse the uploaded file
        data = ProductsFileParser.parse_file(self.file_name, self.import_file)

        batch_size = 50  # Process in batches of 50 rows
        product_data_list = []
        skipped_products = []  # Collect skipped products

        # Process data in batches and collect results
        for start in range(0, len(data), batch_size):
            _logger.info(f"Processing Batch: {start} ~ {start + batch_size}")
            batch = data.iloc[start:start + batch_size]
            for idx, row in batch.iterrows():
                try:
                    _logger.info(f"# Processing Row {idx}")
                    is_skipped, product_data = self.process_row(row)
                    if is_skipped:
                        skipped_products.append(product_data)  # Append product name if skipped
                    elif product_data:
                        product_data_list.append(product_data)  # Append product data if valid
                except Exception as e:
                    raise UserError(f"Error processing row {idx + 1}:\n{e}")

        # Log start of product creation process
        _logger.info("Starting product creation process for all processed rows...")

        # Create products after all rows are processed
        for product_data in product_data_list:
            _logger.info(
                f"# Creating product: {product_data['product_name']} (Mataa ID: {product_data['mataa_id']}, "
                f"Default Code: {product_data['default_code']})")
            ProductService.create_product(
                env=self.with_context(pre_sync=True).env,
                **product_data
            )

        # Display a notification with the skipped products
        if skipped_products:
            skipped_product_names = ", ".join(skipped_products)

            # return {'warning': {
            #     'title': _("Note: Skipped Products (Already Exists)"),
            #     'message': _(f"The following products were skipped: {skipped_product_names}"),
            # }}

    def process_row(self, row):
        mataa_id = row.get('mataa_id')
        default_code = row.get('default_code')
        name = row.get('name')
        description = row.get('description')
        regular_price = row.get('regular_price')
        sales_price = row.get('sales_price')
        brand = row.get('brand')
        # vendor_mataa_id = row.get('vendor_mataa_id')
        # vendor_name = row.get('vendor_name')
        categories = row.get('categories', [])
        attributes = row.get('attributes', [])
        main_image_url = row.get('main_image_url')
        gallery_image_urls = row.get('gallery_image_urls', [])

        # Validate brand and categories
        product_web_categories = []
        for category in categories:
            existing_category = CategoryService.get_web_category(
                env=self.env,
                mataa_id=category.get('mataa_id'),
                category_name=category.get('name')
            )
            if not existing_category:
                raise UserError(f"Category with ID {category.get('mataa_id')} does not exist.")
            product_web_categories.append(existing_category)

        product_brand = BrandService.get_brand_by_name(self.env, brand)
        if not product_brand:
            raise UserError(f"Brand {brand} does not exist.")

        product_category_id = 2
        for category in categories:
            if category.get('mataa_id') in ALLOWED_FUCNTIONAL_CATEGORY_IDS:
                existing_func_category = CategoryService.get_func_category(env=self.env,category_name=category.get('name'))
                product_category_id = existing_func_category.id if existing_func_category else product_category_id
                break

        # product_vendor = VendorService.get_vendor(self.env, vendor_name)
        # if not product_vendor:
        #     raise UserError(f"Vendor {vendor_name} does not exist.")

        # Validate attributes
        product_attribute_values = []
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
            product_attribute_values.append(existing_attribute_value)

        existing_product = ProductService.get_product(self.env, default_code)
        if existing_product:
            return True, f"{mataa_id}:{name}:{default_code}"  # Return skipped status and product name if product exists

        # Collect product data for later creation
        product_data = {
            'mataa_id': mataa_id,
            'product_name': name,
            'description_sale': description,
            'default_code': default_code,
            'regular_price': regular_price,
            'sales_price': sales_price,
            'category_id': product_category_id,
            'product_brand_id': product_brand.id,
            'web_categories': product_web_categories,
            'attribute_values': product_attribute_values,
            'image_urls': ([main_image_url] if main_image_url else []) + gallery_image_urls
        }
        return False, product_data  # Return product data if all validations pass