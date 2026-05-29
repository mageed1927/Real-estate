from urllib.parse import urlparse
from datetime import datetime
from odoo import api, models
from ..services.category_service import CategoryService


class ProductService:

    @staticmethod
    def get_product(env, default_code):
        """Get a product template"""
        product_template = env['product.template'].search([('default_code', '=', default_code)], limit=1)

        return product_template

    @staticmethod
    def get_product_by_mataa_id(env, mataa_id):
        """Get a product template"""
        product_template = env['product.template'].search([('mataa_id', '=', mataa_id)], limit=1)

        return product_template

    @staticmethod
    def create_product(env, mataa_id, product_name, description_sale, default_code, regular_price, sales_price, category_id,
                       product_brand_id, tags=None, web_categories=None, attribute_values=None, image_urls=None):
        """create a product template"""

        if not env['product.category'].browse(category_id).exists():
            raise ValueError("Category ID is invalid")

        product = env['product.template'].create({
            'name': product_name,
            'description_sale': description_sale,
            'default_code': default_code,
            'list_price': sales_price,
            'regular_price': regular_price,
            'categ_id': category_id,
            'product_brand_id': product_brand_id,
            'mataa_id': mataa_id,
            'is_synced': True,
            'mataa_status': 'publish',
            'created_by': 'Initial Sync',
            'last_modified_by': 'Initial Sync',
        })

        # Handle tags
        if tags:
            tag_ids = env['product.tag'].search([('name', 'in', tags)])
            product.write({'tag_ids': [(6, 0, tag_ids.ids)]})

        # Handle categories
        if web_categories:
            CategoryService.assign_public_categories(env, product, web_categories)

        # Handle attributes
        if attribute_values:
            for attribute_value in attribute_values:
                ProductService.assign_product_attribute_values(env, product, attribute_value.attribute_id,
                                                               attribute_value)

        if image_urls and len(image_urls) > 0:
            existing_images = env['product.url'].search([('product_tmpl_id', '=', product.id)], order="sequence desc", limit=1)
            highest_sequence = existing_images.sequence if existing_images else 0

            for index, url in enumerate(image_urls, start=highest_sequence + 1):
                parsed_url = urlparse(url)
                path = parsed_url.path.strip('/')

                # Create the product image record
                env['product.url'].create({
                    'product_tmpl_id': product.id,
                    'url': url,
                    'serialized_name': path if path else f"{datetime.now().strftime('%Y%m%d%H%M%S%f')[:-3]}.jpg",
                    'sequence': index,
                })

        return product

    @staticmethod
    def update_product(env, default_code, product_name=None, regular_price=None, sales_price=None, category_id=None):
        """Get or create a product template"""
        product_template = env['product.template'].search([('default_code', '=', default_code)], limit=1)

        # Update only if there is a change

        product_template.write({
            'name': product_name if product_name and product_template.name != product_name else product_template.name,
            'list_price': sales_price if sales_price and product_template.list_price != sales_price else product_template.list_price,
            'regular_price': regular_price if regular_price and product_template.regular_price != regular_price else product_template.regular_price,
            'categ_id': category_id if category_id and product_template.categ_id.id != category_id else product_template.categ_id,
            'last_modified_by': 'Initial Sync',
        })

        return product_template

    @staticmethod
    def assign_product_attribute_values(env, product_template, attribute, attribute_value):
        # Check if the product template has an attribute line for this attribute
        attribute_line = env['product.template.attribute.line'].search([
            ('product_tmpl_id', '=', product_template.id),
            ('attribute_id', '=', attribute.id)
        ], limit=1)

        if not attribute_line:
            # If no attribute line exists for this attribute, create a new one and assign the attribute value
            attribute_line = env['product.template.attribute.line'].create({
                'product_tmpl_id': product_template.id,
                'attribute_id': attribute.id,
                'value_ids': [(6, 0, [attribute_value.id])]
            })
        else:
            # Check if the attribute value is already associated with the attribute line
            if attribute_value.id not in attribute_line.value_ids.ids:
                # If the attribute value is not associated, append it to the line
                attribute_line.write({
                    'value_ids': [(4, attribute_value.id)]
                })
