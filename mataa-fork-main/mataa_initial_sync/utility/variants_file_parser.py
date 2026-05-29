import base64
import pandas as pd
from collections import defaultdict, deque
from io import BytesIO
from odoo.exceptions import UserError
import json


class VariantsFileParser:
    @staticmethod
    def parse_file(file_name, file_data):
        """Determine the file type and parse accordingly using pandas"""
        if file_name.endswith('.csv'):
            raise UserError("csv parsing is not implemented yet")
        elif file_name.endswith('.xlsx'):
            raise UserError("xlsx parsing is not implemented yet")
        elif file_name.endswith('.json'):
            return VariantsFileParser._parse_json(file_data)
        else:
            raise UserError("Invalid file format. Please upload a CSV or XLSX file.")

    @staticmethod
    def _parse_json(file_data):
        """Parse JSON file, handle nested fields and return data as DataFrame"""
        decoded_file_data = base64.b64decode(file_data).decode('utf-8')
        data = json.loads(decoded_file_data)

        parsed_data = []
        for variant in data:
            base_info = {
                "mataa_id": variant.get("mataa_id"),
                "template_mataa_id": variant.get("parent_id"),
                "default_code": variant.get("default_code"),
                "name": variant.get("name"),
                "regular_price": float(variant.get("regular_price", 0.0)) if variant.get("regular_price") else None,
                "sales_price": float(variant.get("sales_price", 0.0)) if variant.get("sales_price") else None,
                "vendor_product_code": variant.get("ArtNbr"),
                # "SKU": variant.get("SKU"),
                "vendor_product_name": variant.get("Name"),
                # "Price": variant.get("Price"),
                "barcode": str(variant.get("BarCode")) if variant.get("BarCode") else None,
                # "ItemSize": variant.get("ItemSize"),
                # "SportsDescription": variant.get("SportsDescription"),
                # "brand_name": variant.get("Brand"),
                "vendor_quantity": variant.get("Qty"),
                "vendor_name": variant.get("wordpress_vendorName") if variant.get("wordpress_vendorName") != "NULL" else None,
                # "Segments": variant.get("Segments"),
                # "Division": variant.get("Division"),
                # "Breakout": variant.get("Breakout"),
                # "Gender": variant.get("Gender"),
                # "GFR": variant.get("GFR"),
                # "COMM": variant.get("COMM"),
                # "MM": variant.get("MM"),
                # "PricePoint": variant.get("PricePoint"),
                # "SizeScale": variant.get("SizeScale"),
                "vendor_price": variant.get("GenProd"),
                # "Season": variant.get("Season"),
                "attributes": [
                    {
                        "mataa_id": attribute["id"],
                        "name": attribute["name"],
                        "value_mataa_id": attribute["value_id"],
                        "value": attribute["value"],
                    }
                    for attribute in variant.get("attributes", [])]}

            parsed_data.append(base_info)

        # Convert to DataFrame
        df = pd.json_normalize(parsed_data, sep='_')
        df = df.dropna(how='all').reset_index(drop=True)
        df = df.astype(object).where(df.notna(), None)
        return df
