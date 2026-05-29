import io
import base64
import pandas as pd
from io import BytesIO
from odoo.exceptions import UserError
from datetime import datetime
import re

class ImportVariantsErrorFileGenerator:

    @staticmethod
    def _simplify_error_message(err_text: str) -> str:
        if not err_text:
            return err_text

        err_text = re.sub(r"(,?\s*'file_data'\s*:\s*b'[^']*')", "", err_text)

        names = re.findall(r"'file_name'\s*:\s*'([^']+)'", err_text)
        if names:
            return ", ".join(names)

        if len(err_text) > 200:
            return err_text[:200] + "…"
        return err_text

    @staticmethod
    def generate_error_file(obj, data, failed_rows):
        column_names = ['Index'] + list(data.columns) + ['Error Message']

        image_cols = [c for c in data.columns if str(c).startswith('template_images_url')]
        sanitized_rows = []

        for row in failed_rows:
            r = dict(row)
            r['Error Message'] = ImportVariantsErrorFileGenerator._simplify_error_message(
                (r.get('Error Message') or '')
            )

            for col in image_cols:
                val = r.get(col)
                too_long = isinstance(val, str) and len(val) > 255
                looks_like_data_uri = isinstance(val, str) and val.strip().startswith('data:image')
                if too_long or looks_like_data_uri:
                    r[col] = 'the image is invalid'
            sanitized_rows.append(r)

        df = pd.DataFrame(sanitized_rows, columns=column_names)

        output = io.BytesIO()
        df.to_excel(output, index=False, engine='openpyxl')
        output.seek(0)
        b64 = base64.b64encode(output.getvalue())

        # Store as attachment
        attachment = obj.env['ir.attachment'].create({
            'name': f'Import_Errors_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx',
            'type': 'binary',
            'datas': b64,
            'res_model': obj._name,
            'res_id': obj.id or 0,
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        })

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=1',
            'target': 'self',
        }