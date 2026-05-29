# services/import_api_service.py
from odoo.exceptions import UserError
from odoo.fields import Command

from ..services.attribute_service import AttributeService
from ..services.category_service import CategoryService
from ..services.product_service import ProductService
from ..services.tag_service import TagService
from ..services.variant_service import VariantService
from ..services.vendor_service import VendorService
from ..services.brand_service import BrandService

class ImportApiService:

    @staticmethod
    def _parse_attribute_values(row_dict):
        """
        Accepts either:
        - "attributes": [{"name": "Color", "value": "Red"}, ...]
        OR
        - "attributes_string": "Color:Red|Size:M"  (backwards compatible helper)
        """
        values = []

        if isinstance(row_dict.get('attributes'), list):
            for av in row_dict['attributes']:
                name = (av.get('name') or '').strip()
                val = (av.get('value') or '').strip()
                if name and val:
                    values.append((name, val))
            return values

        attrs_str = row_dict.get('attributes_string')
        if attrs_str:
            parts = [p.strip() for p in attrs_str.split('|') if p.strip()]
            for p in parts:
                if ':' in p:
                    n, v = p.split(':', 1)
                    if n.strip() and v.strip():
                        values.append((n.strip(), v.strip()))
        return values

    @staticmethod
    def _parse_product_images(row_dict):
        """
        Accepts either:
        - "image_urls": ["https://.../a.jpg", "https://.../b.png"]
        OR
        - "template_images_url": "https://.../a.jpg, https://.../b.png"
        """
        urls = []
        if isinstance(row_dict.get('image_urls'), list):
            urls = [u for u in row_dict['image_urls'] if isinstance(u, str) and u.strip()]
        elif row_dict.get('template_images_url'):
            urls = [u.strip() for u in str(row_dict['template_images_url']).split(',') if u and u.strip()]
        return urls

    @staticmethod
    def process_row(env, row_dict, behaviour="create_update"):

        template_internal_ref = row_dict.get('template_internal_ref')
        template_name = row_dict.get('template_name')
        template_brand = row_dict.get('template_brand')
        template_functional_category = row_dict.get('template_functional_category')
        template_regular_price = row_dict.get('template_regular_price')
        template_sales_price = row_dict.get('template_sales_price')
        template_web_categories = row_dict.get('template_web_categories')
        template_internal_note = row_dict.get('template_internal_note')
        template_tags = row_dict.get('template_tags')
        template_description = row_dict.get('template_Description') or row_dict.get('template_description')

        variant_internal_ref = row_dict.get('variant_internal_ref')
        variant_name = row_dict.get('variant_name')
        variant_regular_price = row_dict.get('variant_regular_price')
        variant_barcodes = str(row_dict.get('variant_barcodes')) if row_dict.get('variant_barcodes') else None
        variant_tags = row_dict.get('variant_tags')

        vendor_name = row_dict.get('variant_vendor_name')
        vendor_product_name = row_dict.get('variant_vendor_product_name')
        vendor_code = row_dict.get('variant_vendor_product_code')
        vendor_price = row_dict.get('variant_vendor_price')
        vendor_quantity = row_dict.get('variant_vendor_quantity')

        if not template_internal_ref:
            raise UserError("template_internal_ref is required.")

        if vendor_name and vendor_price is not None:
            vendor = VendorService.get_vendor(env, vendor_name=vendor_name)
            if not vendor:
                raise UserError("Vendor not found. Please create the vendor first.")

        category = None
        if template_functional_category:
            category = CategoryService.get_or_create_category(env, template_functional_category)

        brand = None
        if template_brand:
            brand = BrandService.get_brand_by_name(env, template_brand)

        seo_keywords = row_dict.get('seo_keywords')

        if seo_keywords:
            seo_keyword_names = {keyword.strip() for keyword in seo_keywords.split(',')}
            existing_keywords = env['product.seo.keyword'].sudo().search([('name', 'in', list(seo_keyword_names))])
            existing_keyword_names = set(existing_keywords.mapped('name'))
            new_keywords = seo_keyword_names - existing_keyword_names
            new_seo_keywords = env['product.seo.keyword'].sudo().create([{'name': name} for name in new_keywords])

            all_seo_keyword_ids = existing_keywords.ids + new_seo_keywords.ids
        else:
            all_seo_keyword_ids = []

        product_template = ProductService.get_product(env=env, default_code=template_internal_ref)
        if not product_template and behaviour == "only_update":
            raise UserError(
                f"Product Template not found for Internal Ref {template_internal_ref}. "
                f"Switch behaviour to create_update to create a new template."
            )

        product_urls = []
        sequence = 1
        for image_url in ImportApiService._parse_product_images(row_dict):
            stream = ProductService.get_stream(image_url)
            if stream:
                vals = ProductService.get_image_url_vals(image_url, stream)
                vals.update({'sequence': sequence})
                product_urls.append(Command.create(vals))
                sequence += 1

        if product_template:
            product_template = ProductService.update_product(
                env=env,
                product_name=template_name,
                default_code=template_internal_ref,
                regular_price=template_regular_price,
                sales_price=template_sales_price,
                category_id=category.id if category else None,
                description_sale=template_description,
                internal_note=template_internal_note,
                image_url_ids=product_urls,
                brand_id=brand.id if brand else None
            )
        else:
            product_template = ProductService.create_product(
                env=env,
                product_name=template_name,
                default_code=template_internal_ref,
                regular_price=template_regular_price,
                sales_price=template_sales_price,
                category_id=category.id if category else None,
                description_sale=template_description,
                internal_note=template_internal_note,
                image_url_ids=product_urls,
                brand_id=brand.id if brand else None
            )

        if all_seo_keyword_ids:
            product_template.write({
                'product_seo_keywords': [(6, 0, all_seo_keyword_ids)]  # Set SEO keywords on the template
            })

        if template_web_categories:
            for path in str(template_web_categories).split(','):
                CategoryService.get_or_create_web_category(env, path.strip())
            CategoryService.assign_public_categories(env, product_template, template_web_categories)

        if template_tags:
            TagService.assign_tags(env, product_template, template_tags)

        if not variant_internal_ref:
            return {"template_id": product_template.id, "variant_id": None}

        attribute_value_ids = set()
        if behaviour == "create_update":
            for attr_name, value_name in ImportApiService._parse_attribute_values(row_dict):
                attribute = AttributeService.get_or_create_attribute(env, attr_name.strip())
                attribute_value = AttributeService.get_or_create_attribute_value(env, attribute, value_name.strip())
                ProductService.assign_product_attribute_values(env, product_template, attribute, attribute_value)
                attribute_value_ids.add(attribute_value.id)

        if behaviour == "create_update":
            variant = VariantService.update_variant_with_attributes(
                env=env,
                product_template=product_template,
                variant_name=variant_name,
                internal_ref=variant_internal_ref,
                regular_price=variant_regular_price,
                barcodes=variant_barcodes.split(',') if variant_barcodes else None,
                attribute_values=attribute_value_ids
            )
        else:
            variant = VariantService.update_variant(
                env=env,
                product_template=product_template,
                variant_name=variant_name,
                internal_ref=variant_internal_ref,
                regular_price=variant_regular_price,
                barcodes=variant_barcodes.split(',') if variant_barcodes else None,
            )

        if variant_tags:
            TagService.assign_tags(env, variant, variant_tags)

        if vendor_name and vendor_price is not None:
            vendor = VendorService.get_vendor(env, vendor_name=vendor_name)
            VendorService.link_vendor_to_variant(
                env,
                vendor=vendor,
                product_variant=variant,
                vendor_product_name=vendor_product_name,
                vendor_code=vendor_code,
                vendor_price=vendor_price,
                vendor_quantity=vendor_quantity
            )

        env['product.supplierinfo'].check_prices(
            variant, vendor_price, template_sales_price, variant_regular_price
        )

        return {"template_id": product_template.id, "variant_id": variant.id}
