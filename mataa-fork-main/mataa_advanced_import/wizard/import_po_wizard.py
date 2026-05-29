

from odoo import models, fields, api
from odoo.fields import Command
from odoo.exceptions import UserError

from ..services.purchase_order_service import PurchaseOrderService
from ..utility.import_variants_file_parser import ImportVariantsFileParser
from ..utility.import_variants_error_file_generator import ImportVariantsErrorFileGenerator
from ..services.attribute_service import AttributeService
from ..services.category_service import CategoryService
from ..services.product_service import ProductService
from ..services.tag_service import TagService
from ..services.variant_service import VariantService
from ..services.vendor_service import VendorService
from ..services.brand_service import BrandService


class ImportPoWizard(models.TransientModel):
    _name = 'import.po.wizard'
    _description = 'Import POs with variant creation '

    import_file = fields.Binary(string="Upload File", required=True)
    file_name = fields.Char(string="File Name")

    def import_po(self):
        """Main method for importing and processing po"""
        if not self.import_file:
            raise UserError("No file uploaded.")

        # Parse the uploaded file
        data = ImportVariantsFileParser.parse_file(self.file_name, self.import_file)
        failed_rows = []
        purchase_orders = {}
        for idx, row in data.iterrows():
            try:
                purchase_orders.update(self.process_row(row, purchase_orders))
            except Exception as e:
                row_dict = row.fillna('').to_dict()
                row_dict['Index'] = idx + 1
                row_dict['Error Message'] = str(e)
                failed_rows.append(row_dict)
        if failed_rows:
            return ImportVariantsErrorFileGenerator.generate_error_file(self, data, failed_rows)
        return None

    def process_row(self, row, purchase_orders):
        # Template details
        template_internal_ref = row.get('template_internal_ref')
        template_name = row.get('template_name')
        # template_brand = row.get('template_brand')
        template_functional_category = row.get('template_functional_category')
        template_regular_price = row.get('template_regular_price')
        template_sales_price = row.get('template_sales_price')
        # template_web_categories = row.get('template_web_categories')
        # template_internal_note = row.get('template_internal_note')
        # template_tags = row.get('template_tags')
        # template_description = row.get('template_Description')

        # Variant details
        variant_internal_ref = row.get('variant_internal_ref')
        # variant_name = row.get('variant_name')
        variant_regular_price = row.get('variant_regular_price')
        variant_barcodes = str(row.get('variant_barcodes')) if row.get('variant_barcodes') else None
        # variant_tags = row.get('variant_tags')

        # Vendor details
        vendor_name = row.get('variant_vendor_name')
        # vendor_product_name = row.get('variant_vendor_product_name')
        # vendor_code = row.get('variant_vendor_product_code')
        vendor_price = row.get('variant_vendor_price')
        vendor_quantity = row.get('variant_vendor_quantity')
        package_name = row.get('package')

        variant_attribute_values = ImportVariantsFileParser.parse_attribute_values(row)
        # if self.behaviour == "create_update":
        #     variant_attribute_values = ImportVariantsFileParser.parse_attribute_values(row)

        if not template_internal_ref:
            return  # Skip rows without a template name

        # TODO : input data validation

        # validate that the vendor exists
        if vendor_name:
            vendor = VendorService.get_vendor(self.env, vendor_name=vendor_name)
            if not vendor:
                raise UserError("vendor wasn't found , it needs to be created first")
        else:
            raise UserError("vendor name wasn't found , it's required!")

        # Start of the import process

        category = None
        if template_functional_category:
            category = CategoryService.get_or_create_category(self.env, template_functional_category)
        #
        # brand = None
        # if template_brand:
        #     brand = BrandService.get_brand_by_name(self.env, template_brand)

        product_template = ProductService.get_product(env=self.env, default_code=template_internal_ref)
        # if product_template:
        #     raise UserError(f"Product Template exist already for Internal Ref {template_internal_ref}, "
        #                     "It's not allowed to update from here.")

        # Collect separate image columns
        # separate_image_urls = ImportVariantsFileParser.parse_product_images(row)

        # Create images
        # product_urls = []
        # sequence = 1

        # Process images from the template_images_url field
        # if separate_image_urls:
        #     for image_url in separate_image_urls:
        #         image_stream = ProductService.get_stream(image_url.strip())
        #         if image_stream:
        #             image_url_vals = ProductService.get_image_url_vals(image_url, image_stream)
        #             image_url_vals.update({'sequence': sequence})
        #             product_urls.append(Command.create(image_url_vals))
        #             sequence += 1

        # if product_template:
        #     product_template = ProductService.update_product(
        #         env=self.env,
        #         product_name=template_name,
        #         default_code=template_internal_ref,
        #         regular_price=template_regular_price,
        #         sales_price=template_sales_price,
        #         category_id=category.id if category else None,
        #         description_sale=template_description,
        #         internal_note=template_internal_note,
        #         image_url_ids=product_urls,
        #         brand_id=brand.id if brand else None
        #     )
        # else:
        if not product_template:
            product_template = ProductService.create_product(
                env=self.env,
                product_name=template_name,
                default_code=template_internal_ref,
                regular_price=template_regular_price,
                sales_price=template_sales_price,
                category_id=category.id,
                description_sale='',
            )

        if not variant_internal_ref:
            return  # Skip rows without a variant ref

        # Assign attribute values to the product template
        attribute_value_ids = set()
        if variant_attribute_values:
            for attr_name, value_name in variant_attribute_values:
                attribute = AttributeService.get_or_create_attribute(self.env, attr_name.strip())
                attribute_value = AttributeService.get_or_create_attribute_value(self.env, attribute,
                                                                                 value_name.strip())
                ProductService.assign_product_attribute_values(self.env, product_template, attribute, attribute_value)
                attribute_value_ids.add(attribute_value.id)

        product_variant = VariantService.update_variant_with_attributes(
            env=self.env,
            product_template=product_template,
            variant_name='',
            internal_ref=variant_internal_ref,
            regular_price=variant_regular_price,
            barcodes=variant_barcodes.split(',') if variant_barcodes else None,
            attribute_values=attribute_value_ids
        )

        # Handle variant tags
        # if variant_tags:
        #     TagService.assign_tags(self.env, product_variant, variant_tags)

        # Handle vendor information
        if vendor_name and vendor_price is not None:  # Check for vendor name and price
            vendor = VendorService.get_vendor(self.env, vendor_name=vendor_name)

            VendorService.link_vendor_to_variant(
                self.env,
                vendor=vendor,
                product_variant=product_variant,
                # vendor_product_name=vendor_product_name,
                # vendor_code=vendor_code,
                vendor_price=vendor_price,
                vendor_quantity=0)

        # Check vendor price with sale and regular price
        self.env['product.supplierinfo'].check_prices(product_variant, vendor_price, template_sales_price,
                                                      variant_regular_price)
        new_order = {}
        if purchase_orders.get(vendor_name, False):
            order = self.env['purchase.order'].browse(purchase_orders[vendor_name])
            if order:
                PurchaseOrderService.create_order_line(self.env, order, product_variant, vendor_quantity, vendor_price, package_name)
        else:
            order = PurchaseOrderService.create_order(self.env, vendor)
            PurchaseOrderService.create_order_line(self.env, order, product_variant, vendor_quantity, vendor_price, package_name)
            new_order.update({
                vendor_name: order.id
            })
        return new_order
