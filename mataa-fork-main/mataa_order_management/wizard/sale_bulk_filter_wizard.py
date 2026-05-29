# -*- coding: utf-8 -*-

# Add new imports for pandas and io
import base64
import io
try:
    import pandas as pd
except ImportError:
    pd = None

from odoo import models, fields, api
from odoo.exceptions import UserError

class SaleBulkFilterWizard(models.TransientModel):
    _name = 'sale.bulk.filter.wizard'
    _description = 'Wizard to filter Sale Orders by a list of names'

    order_names_text = fields.Text(
        string="Order Numbers",
        help="Paste order numbers here, separated by commas, spaces, or new lines."
    )
    order_names_file = fields.Binary(
        string="Or Upload File (.xlsx, .csv, .txt)",
        help="Upload an Excel, CSV, or Text file with one order number per line in the first column."
    )
    file_name = fields.Char("File Name")

    def apply_filter(self):
        self.ensure_one()
        order_names_list = []

        # Process data from the text field first
        if self.order_names_text:
            raw_list = self.order_names_text.replace(',', '\n').split('\n')
            order_names_list = [name.strip() for name in raw_list if name.strip()]

        # If no text, process data from the uploaded file
        elif self.order_names_file:
            # Check if pandas is installed
            if pd is None:
                raise UserError("The 'pandas' Python library is not installed. Please install it to use the Excel upload feature (pip install pandas).")

            try:
                # Decode the file from base64
                decoded_file = base64.b64decode(self.order_names_file)

                # Read based on file type
                if self.file_name and self.file_name.endswith('.xlsx'):
                    # Use pandas to read the excel file from memory
                    file_like_object = io.BytesIO(decoded_file)
                    df = pd.read_excel(file_like_object, engine='openpyxl')
                    # Get data from the first column, convert to string, and clean it
                    raw_list = df.iloc[:, 0].dropna().astype(str).tolist()
                    order_names_list = [name.strip() for name in raw_list if name.strip()]
                else:
                    # Fallback for .txt or .csv files
                    file_content = decoded_file.decode('utf-8')
                    raw_list = file_content.splitlines()
                    order_names_list = [name.strip() for name in raw_list if name.strip()]

            except Exception as e:
                raise UserError(f"Could not read the file. Please ensure it is a valid format.\n\nError: {e}")

        if not order_names_list:
            return {'type': 'ir.actions.act_window_close'}

        domain = [('name', 'in', order_names_list)]

        return {
            'name': 'Filtered Sale Orders',
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'view_mode': 'tree,form',
            'views': [(self.env.ref('sale.view_quotation_tree_with_onboarding').id, 'tree'), (False, 'form')],
            'domain': domain,
            'target': 'current',
        }