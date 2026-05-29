import base64
import pandas as pd
from io import BytesIO
from odoo.exceptions import UserError


class ImportPackagesFileParser:
    @staticmethod
    def parse_file(file_name, file_data):
        """Determine the file type and parse accordingly using pandas"""
        if file_name.endswith('.csv'):
            raise UserError("csv parsing is not implemented yet , please convert your files into xlsx format")
        elif file_name.endswith('.xlsx'):
            return ImportPackagesFileParser._parse_xlsx(file_data)
        else:
            raise UserError("Invalid file format. Please upload a CSV or XLSX file.")

    @staticmethod
    def _parse_xlsx(file_data):
        """Parse XLSX file using pandas and return data"""
        decoded_file_data = base64.b64decode(file_data)
        file_stream = BytesIO(decoded_file_data)

        data_types = {
            'product-variant-barcode': str,
            'package-name': str,
            'quantity': float,
        }

        df = pd.read_excel(file_stream, engine='openpyxl', dtype=data_types)
        df = df.dropna(how='all').reset_index(drop=True)
        df = df.astype(object).where(df.notna(), None)

        if not isinstance(df, pd.DataFrame):
            raise UserError("Parsed data is not in the expected format.")

        return df
