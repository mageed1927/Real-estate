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

class FilterFromFileWizard(models.TransientModel):
    _name = 'filter.from.file.wizard'
    _description = 'Wizard to filter unsynced products from the imported xlsx file'

    import_file = fields.Binary(string="Upload Excel Sheet", required=True)
    file_name = fields.Char(string="File Name")

    def filter_from_file(self):
        self.ensure_one()
        products_ref_list = []

        if pd is None:
            raise UserError("The pandas library is not installed. please install it using 'pip install pandas'")
        
        try:
            decoded_file = base64.b64decode(self.import_file)
            file_like_object = io.BytesIO(decoded_file)
            df = pd.read_excel(file_like_object, engine='openpyxl')
            products_ref_list = df.iloc[:, 0].dropna().astype(str).tolist()
        except Exception as e:
            raise UserError(f"Error reading the file: {e}")
        
        if not products_ref_list:
            return {'type': 'ir.actions.act_window_close'}
        
        # Filter by default_code and ensure they are unsynced
        domain = [('default_code', 'in', products_ref_list), ('is_synced', '=', False)]
        
        return {
            'name': 'Filtered Unsynced Products',
            'type': 'ir.actions.act_window',
            'res_model': 'product.template',
            'view_mode': 'tree,form',
            'views': [(self.env.ref('mataa_external_sync.view_product_template_unsynced_tree').id, 'tree')],
            'domain': domain,
            'target': 'current'
        }