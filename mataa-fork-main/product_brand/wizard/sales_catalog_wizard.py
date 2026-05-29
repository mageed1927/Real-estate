import io
import json
import base64
import requests
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from odoo import models, fields, api, _
from odoo.tools.misc import xlsxwriter
from PIL import Image

class SalesCatalogWizard(models.TransientModel):
    _name = 'product.brand.sales.wizard'
    _description = 'Sales Catalog Wizard'

    def _fetch_image_from_url(self, url):
        try:
            res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=2)
            if res.status_code == 200:
                return io.BytesIO(res.content)
        except:
            return None
        return None

    @api.model
    def generate_catalog(self, json_data_str):
        jdata = json.loads(json_data_str) if json_data_str else {}
        
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        title = jdata.get('title', 'Sales Catalog')
        worksheet = workbook.add_worksheet(title[:31])

        # 1. Define Excel Formats & Styles
        header_plain = workbook.add_format({'pattern': 1, 'bg_color': '#D3D3D3', 'border': 1, 'valign': 'vcenter'})
        header_bold = workbook.add_format({'bold': True, 'pattern': 1, 'bg_color': '#D3D3D3', 'border': 1, 'align': 'center', 'valign': 'vcenter'})
        bold_style = workbook.add_format({'bold': True, 'border': 1, 'valign': 'vcenter'})
        normal_style = workbook.add_format({'border': 1, 'valign': 'vcenter'})
        row_header_style = workbook.add_format({'pattern': 1, 'bg_color': '#F2F2F2', 'border': 1, 'valign': 'vcenter'})
        total_header_style = workbook.add_format({'bold': True, 'pattern': 1, 'bg_color': '#E6E6E6', 'border': 1, 'valign': 'vcenter'})

        DATA_OFFSET = 2 

        # 2. Setup Static Columns (Image & Title)
        worksheet.set_column(0, 0, 15) 
        worksheet.write(0, 0, "Image", header_bold)
        
        worksheet.set_column(1, 1, 45)
        worksheet.write(0, 1, "Total", header_plain)

        # Extract configuration and data from JSON
        measure_count = jdata.get('measure_count', 1)
        origin_count = jdata.get('origin_count', 1)
        col_group_headers = jdata.get('col_group_headers', [])
        measure_headers = jdata.get('measure_headers', [])
        origin_headers = jdata.get('origin_headers', [])
        rows = jdata.get('rows', [])


        x, y, carry = 0, 0, deque()
        if col_group_headers:
            for i, header_row in enumerate(col_group_headers):
                worksheet.write(i, 0, "", header_plain) 
                worksheet.write(i, 1, "", header_plain)
                for header in header_row:
                    while (carry and carry[0]['x'] == x):
                        cell = carry.popleft()
                        for j in range(measure_count * (2 * origin_count - 1)):
                            worksheet.write(y, x + j + DATA_OFFSET, '', header_plain)
                        if cell['height'] > 1:
                            carry.append({'x': x, 'height': cell['height'] - 1})
                        x = x + measure_count * (2 * origin_count - 1)
                    h_width = header.get('width', 1)
                    h_height = header.get('height', 1)
                    h_title = header.get('title', '')
                    for j in range(h_width):
                        worksheet.write(y, x + j + DATA_OFFSET, h_title if j == 0 else '', header_plain)
                    if h_height > 1:
                        carry.append({'x': x, 'height': h_height - 1})
                    x = x + h_width
                while (carry and carry[0]['x'] == x):
                    cell = carry.popleft()
                    for j in range(measure_count * (2 * origin_count - 1)):
                        worksheet.write(y, x + j + DATA_OFFSET, '', header_plain)
                    if cell['height'] > 1:
                        carry.append({'x': x, 'height': cell['height'] - 1})
                    x = x + measure_count * (2 * origin_count - 1)
                x, y = 0, y + 1

        if measure_headers:
            worksheet.write(y, 0, '', header_plain)
            worksheet.write(y, 1, '', header_plain)
            for measure in measure_headers:
                style = header_bold if measure.get('is_bold') else header_plain
                worksheet.write(y, x + DATA_OFFSET, measure.get('title', ''), style)
                for i in range(1, 2 * origin_count - 1):
                    worksheet.write(y, x + i + DATA_OFFSET, '', header_plain)
                x = x + (2 * origin_count - 1)
            x, y = 0, y + 1
            for i in range(len(measure_headers)):
                 worksheet.set_column(i + DATA_OFFSET, i + DATA_OFFSET, 16)

        if origin_headers:
            worksheet.write(y, 0, '', header_plain)
            worksheet.write(y, 1, '', header_plain)
            for origin in origin_headers:
                style = header_bold if origin.get('is_bold') else header_plain
                worksheet.write(y, x + DATA_OFFSET, origin.get('title', ''), style)
                x = x + 1
            y = y + 1

        if y > 0:
            worksheet.freeze_panes(y, 1)

        urls_to_fetch = {}
        fetched_images = {}

        all_product_ids = []
        row_indices_with_products = {}

        for idx, row in enumerate(rows):
            p_id = row.get('product_id')
            
            if p_id:
                all_product_ids.append(p_id)
                row_indices_with_products[idx] = p_id


        unique_ids = list(set(all_product_ids))
        products_map = {}
        for p_id in unique_ids:
            product = self.env['product.product'].sudo().browse(p_id)
            if not product.exists():
                product = self.env['product.template'].sudo().browse(p_id)
            if product.exists():
                products_map[p_id] = product

        for idx, p_id in row_indices_with_products.items():
            if p_id in products_map:
                prod = products_map[p_id]
                url_recs = getattr(prod, 'image_url_ids', None)
                if url_recs and len(url_recs) > 0 and url_recs[0].url:
                     urls_to_fetch[idx] = url_recs[0].url

        if urls_to_fetch:
            with ThreadPoolExecutor(max_workers=4) as executor:
                future_to_index = {
                    executor.submit(self._fetch_image_from_url, url): idx 
                    for idx, url in urls_to_fetch.items()
                }
                
                for future in as_completed(future_to_index):
                    idx = future_to_index[future]
                    try:
                        data = future.result()
                        if data:
                            fetched_images[idx] = data
                    except Exception:
                        pass
    
        for idx, row in enumerate(rows):
            img_done = False

            if idx in fetched_images:
                x_target = 102
                y_teaget = 126
                image_stream = fetched_images[idx]
                img = Image.open(image_stream)
                w, h = img.size
                x_scale = x_target/w 
                y_scale = y_teaget/h
                
                worksheet.set_row(y, 100)
                worksheet.insert_image(y, 0, "img.png", {'image_data': fetched_images[idx], 'x_scale':x_scale, 'y_scale': y_scale, 'object_position': 1, 'x_offset': 7, 'y_offset': 5})
                img_done = True

            if not img_done:
                 style = total_header_style if row.get('indent') == 0 else row_header_style
                 worksheet.write(y, 0, "", style)

            indent = row.get('indent', 0)
            title_text = indent * '    ' + str(row.get('title', ''))
            
            current_row_style = total_header_style if indent == 0 else row_header_style
            worksheet.write(y, 1, title_text, current_row_style)

            x_val = 0
            for cell in row.get('values', []):
                val = cell.get('value')
                style = bold_style if cell.get('is_bold') else normal_style
                if indent == 0: style = total_header_style
                
                worksheet.write(y, x_val + DATA_OFFSET, val, style)
                x_val += 1
            
            y += 1


        # Finalize
        workbook.close()
        output.seek(0)
        file_data = base64.b64encode(output.read())
        output.close()

        attachment = self.env['ir.attachment'].create({
            'name': f"{title}.xlsx",
            'type': 'binary',
            'datas': file_data,
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        })

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }