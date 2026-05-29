import base64
import pandas as pd
from collections import defaultdict, deque
from io import BytesIO
from odoo.exceptions import UserError


class CustomersFileParser:
    @staticmethod
    def parse_file(file_name, file_data):
        """Determine the file type and parse accordingly using pandas"""
        if file_name.endswith('.csv'):
            raise UserError("csv parsing is not implemented yet , please convert your files into xlsx format")
        elif file_name.endswith('.xlsx'):
            return CustomersFileParser._parse_xlsx(file_data)
        else:
            raise UserError("Invalid file format. Please upload a CSV or XLSX file.")

    @staticmethod
    def _parse_xlsx(file_data):
        """Parse XLSX file using pandas and return data"""
        decoded_file_data = base64.b64decode(file_data)
        file_stream = BytesIO(decoded_file_data)

        data_types = {
            'customer_id': int,
            'address_1': str,
            'address_2': str,
            'country': str,
            'state_name': str,
            'user_email': str,
            'display_name': str,
            'date_of_birth': str,
            'first_name': str,
            'last_name': str,
            'sex': str,
            'registered_phone_number': str
        }

        df = pd.read_excel(file_stream, engine='openpyxl', dtype=data_types)
        df = df.dropna(how='all').reset_index(drop=True)
        df = df.astype(object).where(df.notna(), None)

        if not isinstance(df, pd.DataFrame):
            raise UserError("Parsed data is not in the expected format.")

        return df