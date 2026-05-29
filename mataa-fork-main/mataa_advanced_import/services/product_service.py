import base64
import logging
import time # Import time for delays
from PIL import Image
from io import BytesIO
import random # Import random for User-Agent selection

from odoo import api, models

import requests
from urllib.parse import urlparse

_logger = logging.getLogger(__name__)


class ProductService:

    @staticmethod
    def get_product(env, default_code):
        """Get a product template"""
        product_template = env['product.template'].sudo().search([('default_code', '=', default_code)], limit=1)

        return product_template

    @staticmethod
    def create_product(env, product_name, default_code, regular_price, sales_price, category_id, description_sale, internal_note=None, brand_id=None, image_url_ids=None):
        """create a product template"""
        product_template = env['product.template'].with_context(skip_vendor_price_check=True).sudo().create({
            'name': product_name,
            'default_code': default_code,
            'list_price': sales_price,
            'regular_price': regular_price,
            'categ_id': category_id,
            'description': internal_note,
            'description_sale': description_sale,
            'product_brand_id': brand_id,
            'image_url_ids': image_url_ids,
            'created_by': 'Advanced Import',
            'last_modified_by': 'Advanced Import',
        })

        return product_template

    @staticmethod
    def update_product(env, default_code, product_name=None, regular_price=None, sales_price=None, category_id=None,
                       internal_note=None, description_sale=None, brand_id=None, image_url_ids=None):
        """Get or create a product template"""
        product_template = env['product.template'].sudo().search([('default_code', '=', default_code)], limit=1)

        # Update only if there is a change

        product_template.with_context(skip_vendor_price_check=True).sudo().write({
            'name': product_name if product_name and product_template.name != product_name else product_template.name,
            'list_price': sales_price if sales_price and product_template.list_price != sales_price else product_template.list_price,
            'regular_price': regular_price if regular_price and product_template.regular_price != regular_price else product_template.regular_price,
            'categ_id': category_id if category_id and product_template.categ_id.id != category_id else product_template.categ_id.id,
            'description': internal_note if internal_note and product_template.description != internal_note else product_template.description,
            'description_sale': description_sale if description_sale and product_template.description_sale != description_sale else product_template.description_sale,
            'product_brand_id':
                brand_id
                if brand_id and product_template.product_brand_id.id != brand_id
                else product_template.product_brand_id.id if product_template.product_brand_id else None,
            'image_url_ids': image_url_ids,
            'last_modified_by': 'Advanced Import',
        })

        return product_template

    @staticmethod
    def assign_product_attribute_values(env, product_template, attribute, attribute_value):
        # Check if the product template has an attribute line for this attribute
        attribute_line = env['product.template.attribute.line'].sudo().search([
            ('product_tmpl_id', '=', product_template.id),
            ('attribute_id', '=', attribute.id)
        ], limit=1)

        if not attribute_line:
            # If no attribute line exists for this attribute, create a new one and assign the attribute value
            attribute_line = env['product.template.attribute.line'].sudo().create({
                'product_tmpl_id': product_template.id,
                'attribute_id': attribute.id,
                'value_ids': [(6, 0, [attribute_value.id])]
            })
        else:
            # Check if the attribute value is already associated with the attribute line
            if attribute_value.id not in attribute_line.value_ids.ids:
                # If the attribute value is not associated, append it to the line
                attribute_line.sudo().write({
                    'value_ids': [(4, attribute_value.id)]
                })

    @staticmethod
    def get_stream(image_url):
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15'
        ]
        headers = {
            'User-Agent': random.choice(user_agents), # Randomly select a User-Agent
            'Referer': image_url, # Keep Referer as the image URL itself
            'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8' # Accept image types
        }
        max_retries = 5 # Increased retries
        for i in range(max_retries):
            try:
                response = requests.get(image_url, headers=headers, stream=True, timeout=15) # Increased timeout to 15 seconds
                if response.status_code == 200:
                    image_bytes = response.content
                    if not image_bytes:
                        raise ValueError("Empty image data received")
                    image = Image.open(BytesIO(image_bytes))
                    image.verify()
                    return image_bytes
                elif response.status_code == 403:
                    _logger.warning(f"Failed to fetch image (403 Forbidden) on attempt {i+1}/{max_retries}. URL: {image_url}")
                    if i < max_retries - 1:
                        time.sleep(2 ** i) # Exponential backoff: 1, 2, 4 seconds
                        continue
                    else:
                        _logger.error(f"Max retries reached for {image_url}. Giving up.")
                        break
                else:
                    _logger.warning(f"Failed to fetch image. Status code: {response.status_code}. URL: {image_url}")
                    break
            except requests.exceptions.RequestException as e:
                _logger.warning(f"Request exception while fetching image on attempt {i+1}/{max_retries}. Error: {e}. URL: {image_url}")
                if i < max_retries - 1:
                    time.sleep(2 ** i)
                    continue
                else:
                    _logger.error(f"Max retries reached for {image_url}. Giving up.")
                    break
        return None

    @staticmethod
    def get_image_url_vals(image_url, image_stream):
        parsed_url = urlparse(image_url)
        filename = parsed_url.path.split('/')[-1]
        return {
            'file_name': filename,
            'file_data': image_stream,
        }
