import base64
import pandas as pd
from collections import defaultdict, deque
from io import BytesIO
from odoo.exceptions import UserError
import json


class ProductsFileParser:
    @staticmethod
    def parse_file(file_name, file_data):
        """Determine the file type and parse accordingly using pandas"""
        if file_name.endswith('.csv'):
            raise UserError("csv parsing is not implemented yet")
        elif file_name.endswith('.xlsx'):
            raise UserError("xlsx parsing is not implemented yet")
        elif file_name.endswith('.json'):
            return ProductsFileParser._parse_json(file_data)
        else:
            raise UserError("Invalid file format. Please upload a CSV or XLSX file.")

    @staticmethod
    def _parse_json(file_data):
        """Parse JSON file, handle nested fields and return data as DataFrame"""
        decoded_file_data = base64.b64decode(file_data).decode('utf-8')
        data = json.loads(decoded_file_data)

        parsed_data = []
        for product in data:
            base_info = {"mataa_id": product.get("mataa_id"),
                         "default_code": product.get("default_code"),
                         "name": product.get("name"),
                         "description": product.get("description"),
                         "regular_price": product.get("regular_price"),
                         "sales_price": product.get("sales_price"),
                         "brand": product.get("brand"),
                         "vendor_mataa_id": product.get("wordpress_vendorId"),
                         "vendor_name": product.get("wordpress_vendorName"),
                         "main_image_url": product.get("main_image_url"),
                         "gallery_image_urls": [
                             url.strip() for url in (product.get("gallery_image_urls", "") or "").split(",") if url.strip()
                         ],
                         "tags": [
                             {
                                 "mataa_id": tag["id"],
                                 "name": tag["name"]
                             }
                             for tag in product.get("tags", [])],
                         "categories": [
                             {
                                 "mataa_id": cat["id"],
                                 "name": cat["name"]
                             }
                             for cat in product.get("categories", [])],
                         "attributes": [
                             {
                                 "mataa_id": attribute["id"],
                                 "name": attribute["name"],
                                 "value_mataa_id": attribute["value_id"],
                                 "value": attribute["value"],
                             }
                             for attribute in product.get("attributes", [])]}

            parsed_data.append(base_info)

        # Convert to DataFrame
        df = pd.json_normalize(parsed_data, sep='_')
        return df
