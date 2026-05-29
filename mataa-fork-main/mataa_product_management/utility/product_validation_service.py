# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
from odoo.exceptions import UserError
from odoo.addons.mataa_advanced_import.services.category_service import CategoryService
import logging

_logger = logging.getLogger(__name__)

class ProductValidationService:

    @staticmethod
    def validate_template_internal_ref(env, ref, exclude_template_id=None):
        if not ref or not str(ref).strip():
            raise UserError("template_internal_ref is required")

        ref = str(ref).strip()

        domain = [('default_code', '=ilike', ref)]
        if exclude_template_id:
            domain.append(('id', '!=', exclude_template_id))

        if env['product.template'].sudo().search(domain, limit=1):           raise UserError(f"Template SKU '{ref}' already exists")

        return ref

    @staticmethod
    def validate_template_name(name):
        if not name:
            raise UserError("template_name is required")
        return str(name).strip()

    @staticmethod
    def validate_brand(env, brand_name):
        brand = env['product.brand'].sudo().search(
            [('name', '=ilike', str(brand_name).strip())],
            limit=1
        )
        if not brand:
            raise UserError(f"Brand not found: {brand_name}")
        return brand

    @staticmethod
    def validate_variant_internal_ref(env, ref, exclude_variant_id=None):
        if not ref:
            raise UserError("variant_internal_ref is required")

        ref = str(ref).strip()
        domain = [('default_code', '=ilike', ref)]

        if exclude_variant_id:
            domain.append(('id', '!=', exclude_variant_id))

        if env['product.product'].sudo().with_context(active_test=False).search(domain, limit=1):
            raise UserError(f"SKU '{ref}' already exists")

        return ref

    @staticmethod
    def validate_variant_price(price):
        if price is None:
            raise UserError("variant_regular_price is required")
        return float(price)

    @staticmethod
    def validate_attributes(attrs):
        if not attrs:
            raise UserError("variant_attributes is required")
        return [
            (str(a['name']).strip(), str(a['value']).strip())
            for a in attrs
        ]

    @staticmethod
    def _validate_vendor_name( vendor_name):
        if not vendor_name or not str(vendor_name).strip():
            raise UserError("variant_vendor_name is required and cannot be empty")
        vendor = request.env['res.partner'].sudo().search([('name', '=', str(vendor_name).strip())], limit=1)
        if not vendor:
            raise UserError(f"Vendor not found: {vendor_name}. Please create the vendor first.")
        return vendor

    @staticmethod
    def _validate_vendor_product_name( vendor_product_name):
        return str(vendor_product_name).strip()

    @staticmethod
    def _validate_vendor_product_code( vendor_product_code):
        if vendor_product_code is not None:
            return str(vendor_product_code).strip() if vendor_product_code else None
        return None

    @staticmethod
    def _validate_vendor_price( vendor_price):
        if vendor_price is None:
            raise UserError("variant_vendor_price is required")
        try:
            vendor_price_float = float(vendor_price)
            if vendor_price_float < 0:
                raise UserError("variant_vendor_price must be a positive number")
            return vendor_price_float
        except (ValueError, TypeError):
            raise UserError("variant_vendor_price must be a valid number")

    @staticmethod
    def _validate_vendor_quantity( vendor_quantity):
        if vendor_quantity is None:
            raise UserError("variant_vendor_quantity is required")
        try:
            vendor_quantity_int = int(vendor_quantity)
            if vendor_quantity_int < 0:
                raise UserError("variant_vendor_quantity must be a non-negative integer")
            return vendor_quantity_int
        except (ValueError, TypeError):
            raise UserError("variant_vendor_quantity must be a valid integer")

    @staticmethod
    def _validate_template_internal_ref(template_internal_ref):
        if not template_internal_ref or not str(template_internal_ref).strip():
            raise UserError("template_internal_ref is required and cannot be empty")
        return str(template_internal_ref).strip()

    @staticmethod
    def _validate_template_name( template_name):
        if not template_name or not str(template_name).strip():
            raise UserError("template_name is required and cannot be empty")
        return str(template_name).strip()

    @staticmethod
    def _validate_template_brand( template_brand):
        brand = request.env['product.brand'].sudo().search([('name', '=ilike', str(template_brand).strip())], limit=1)
        if not brand:
            return None
        return brand

    @staticmethod
    def validate_template_functional_category( template_functional_category):
        if not template_functional_category or not str(template_functional_category).strip():
            raise UserError("template_functional_category cannot be empty")

        category_path = str(template_functional_category).strip()

        if '/' in category_path:
            parent_id = False
            category = None

            for name in [n.strip() for n in category_path.split('/') if n.strip()]:
                category = request.env['product.category'].sudo().search(
                    [('name', '=ilike', name), ('parent_id', '=', parent_id)],
                    limit=1
                )
                if not category:
                    break
                parent_id = category.id

            if category:
                return category

        category = request.env['product.category'].sudo().search(
            [('name', '=ilike', category_path)],
            limit=1
        )

        if not category:
            raise UserError(
                f"Functional category not found: {template_functional_category}. "
                "Please create the category first."
            )

        return category

    @staticmethod
    def _validate_template_regular_price( template_regular_price):
        if template_regular_price is None:
            raise UserError("template_regular_price is required")
        try:
            price_float = float(template_regular_price)
            return price_float
        except:
            raise UserError("template_regular_price must be a valid number")

    @staticmethod
    def _validate_template_sales_price(template_sales_price):
        if template_sales_price is None:
            raise UserError("template_sales_price is required")
        try:
            price_float = float(template_sales_price)
            return price_float
        except:
            raise UserError("template_sales_price must be a valid number")

    @staticmethod
    def validate_template_web_categories(env, categories):

        if categories is None:
            return env['product.public.category']

        Category = env['product.public.category'].sudo()

        # Single integer → convert to list
        if isinstance(categories, int):
            categories = [categories]

        # Comma-separated string → convert to list
        if isinstance(categories, str):
            categories = [c.strip() for c in categories.split(',') if c.strip()]

        if not isinstance(categories, list):
            raise UserError(
                "template_web_categories must be int, list, or comma-separated string"
            )

        if not categories:
            return Category

        # -----------------------------------------
        # Case 1: List of IDs
        # -----------------------------------------
        if all(isinstance(x, int) for x in categories):
            found = Category.search([('id', 'in', categories)])
            missing = set(categories) - set(found.ids)

            if missing:
                raise UserError(f"Web category IDs not found: {sorted(missing)}")

            return found

        # -----------------------------------------
        # Case 2: List of strings (name OR full path)
        # -----------------------------------------
        if all(isinstance(x, str) for x in categories):

            resolved_categories = Category.browse()

            for item in categories:
                item = item.strip()

                # If it looks like a path → use complete path resolver
                if '/' in item:
                    category = CategoryService.get_category_by_complete_path(env, item)
                else:
                    category = Category.search([('name', '=ilike', item)], limit=1)

                if not category:
                    raise UserError(f"Web category not found: {item}")

                resolved_categories |= category

            return resolved_categories

        raise UserError("Invalid format for template_web_categories")

    @staticmethod
    def _validate_template_images_url( template_images_url):
        return [url.strip() for url in template_images_url if url and str(url).strip()]

    @staticmethod
    def _validate_template_internal_note( template_internal_note):
        return str(template_internal_note).strip() if template_internal_note else None

    @staticmethod
    def validate_template_tags(template_tags):
        if template_tags is None:
            return None
        if not isinstance(template_tags, str):
            raise UserError("template_tags must be a string")

        return template_tags.strip() or None

    @staticmethod
    def _validate_template_description( template_description):
        return str(template_description).strip()

    @staticmethod
    def _validate_variant_internal_ref(variant_internal_ref):
        if not variant_internal_ref:
            raise UserError("variant_internal_ref is required")
        return str(variant_internal_ref).strip()

    @staticmethod
    def _validate_variant_name( variant_name):
        if not variant_name:
            raise UserError("variant_name is required")
        return str(variant_name).strip()

    @staticmethod
    def _validate_variant_regular_price( variant_regular_price):
        if variant_regular_price is None:
            raise UserError("variant_regular_price is required")
        return float(variant_regular_price)

    @staticmethod
    def _validate_variant_barcodes( variant_barcodes):
        if not variant_barcodes:
            return []
        return str(variant_barcodes).strip()

    @staticmethod
    def _validate_variant_tags( variant_tags):
        return str(variant_tags).strip() if variant_tags else None

    @staticmethod
    def _validate_variant_attributes(variant_attributes):
        if not variant_attributes:
            raise UserError("variant_attributes is required")
        attribute_value_pairs = []
        if isinstance(variant_attributes, list):
            for attr_obj in variant_attributes:
                attr_name = attr_obj.get('name') or attr_obj.get('attribute')
                attr_value = attr_obj.get('value')
                attribute_value_pairs.append((str(attr_name).strip(), str(attr_value).strip()))
        return attribute_value_pairs

    @staticmethod
    def validate_product_seo_keywords(env, seo_keywords):

        if seo_keywords is None:
            return None

        if isinstance(seo_keywords, str):
            names = [n.strip() for n in seo_keywords.split(',') if n.strip()]
        elif isinstance(seo_keywords, list):
            names = [str(n).strip() for n in seo_keywords if str(n).strip()]
        else:
            raise UserError("product_seo_keywords must be a string or a list of names")

        if not names:
            return []

        keyword_ids = []
        Keyword = env['product.seo.keyword'].sudo()

        for name in names:
            keyword = Keyword.search([('name', '=ilike', name)], limit=1)
            if not keyword:
                keyword = Keyword.create({'name': name})
            keyword_ids.append(keyword.id)

        return keyword_ids

    @staticmethod
    def validate_mataa_status(status):
        if status is None:
            return None

        normalized_status = str(status).strip().lower()
        allowed = {'draft', 'publish'}

        if normalized_status not in allowed:
            raise UserError(
                "mataa_status must be one of: draft, publish"
            )

        return normalized_status
