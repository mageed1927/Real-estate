import base64
import pandas as pd
from io import BytesIO
from odoo.exceptions import UserError


class ImportVariantsFileParser:
    @staticmethod
    def parse_file(file_name, file_data):
        """Determine the file type and parse accordingly using pandas"""
        if file_name.endswith('.csv'):
            raise UserError("csv parsing is not implemented yet , please convert your files into xlsx format")
        elif file_name.endswith('.xlsx'):
            return ImportVariantsFileParser._parse_xlsx(file_data)
        else:
            raise UserError("Invalid file format. Please upload a CSV or XLSX file.")

    @staticmethod
    def parse_attribute_values(row):
        """Extract attribute and value pairs from the row."""
        attribute_values = []

        # Initialize a list to keep track of attribute columns processed
        processed_attributes = set()

        for column in row.index:
            if column.startswith('variant_attribute') and column not in processed_attributes:
                # Get the value of the current attribute
                attribute = row[column]
                # Get the corresponding value from the next column
                next_column_index = row.index.get_loc(column) + 1

                # Check if the next column exists and is named 'value'
                if next_column_index < len(row.index) and row.index[next_column_index].startswith('variant_value'):
                    value = str(row[next_column_index]) if row[next_column_index] else None
                    if attribute and value:
                        attribute_values.append((attribute, value))
                        processed_attributes.add(column)

        return attribute_values

    @staticmethod
    def parse_product_images(row):
        """Extract product images from the row. Returns all valid image URLs from all template_images_url columns."""
        import pandas as pd
        
        product_images = []
        processed_images = set()

        for column in row.index:
            if column.startswith('template_images_url') and column not in processed_images:
                image_url = row[column]
                # Handle pandas NaN, None, and empty values
                if pd.isna(image_url) or image_url is None:
                    processed_images.add(column)
                    continue
                # Convert to string and check if it's not empty
                url_str = str(image_url).strip()
                if url_str and url_str.lower() not in ('nan', 'none', ''):
                    product_images.append(url_str)
                processed_images.add(column)

        return product_images if len(product_images) > 0 else None

    @staticmethod
    def _parse_xlsx(file_data):
        """Parse XLSX file using pandas and return data"""
        decoded_file_data = base64.b64decode(file_data)
        file_stream = BytesIO(decoded_file_data)

        data_types = {
            'template_internal_ref': str,
            'template_name': str,
            'template_brand': str,
            'template_functional_category': str,
            'template_regular_price': float,
            'template_sales_price': float,
            'template_web_categories': str,
            'template_images_url': str,
            'template_internal_note': str,
            'template_tags': str,
            'template_Description': str,
            'variant_internal_ref': str,
            'variant_name': str,
            'variant_regular_price': float,
            'variant_barcodes': str,
            'variant_tags': str,
            'variant_vendor_name': str,
            'variant_vendor_product_name': str,
            'variant_vendor_product_code': str,
            'variant_vendor_price': float,
            'variant_vendor_quantity': int,
            'variant_attribute': str,
            'variant_value': str
        }

        df = pd.read_excel(file_stream, engine='openpyxl', dtype=data_types ,  thousands=',')
        df = df.dropna(how='all').reset_index(drop=True)
        df = df.astype(object).where(df.notna(), None)

        if not isinstance(df, pd.DataFrame):
            raise UserError("Parsed data is not in the expected format.")

        return df
