import os

import io
import xlsxwriter
from ..constants.custom_product_export_constants import FILE_COLUMNS, TYPE_COLUMNS


class CustomExportUtility:

    @staticmethod
    def export_products(products):
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {"in_memory": True})
        worksheet = workbook.add_worksheet('')
        header_format = workbook.add_format({"bold": True})
        max_variant_values = max(len(prod.product_template_variant_value_ids) for prod in products)
        CustomExportUtility.create_header(worksheet, header_format, max_variant_values)
        line_index = 1
        for product in products:
            nb_vendor_lines = max(len(product.mapped('variant_seller_ids').filtered(
                lambda seller: seller.product_id.id == product.id)), 1)
            for j in range(0, nb_vendor_lines):
                CustomExportUtility.add_product_info(product, line_index, worksheet, max_variant_values, j)
                line_index += 1
        workbook.close()
        xlsx_data = output.getvalue()
        return xlsx_data

    @staticmethod
    def create_header(worksheet, header_format, max_variant_values):
        i = 0
        for col in FILE_COLUMNS:
            if i == 12:
                for j in range(0, max_variant_values):
                    worksheet.write_string(0, i, 'variant_attribute', header_format)
                    i += 1
                    worksheet.write_string(0, i, 'variant_value', header_format)
                    i += 1
            worksheet.write_string(0, i, col, header_format)
            i += 1

    @staticmethod
    def add_product_info(product, line_index, worksheet, max_variant_values, seller_index):
        i = 0
        for col in FILE_COLUMNS:
            if i == 12:
                for ptav in product.product_template_variant_value_ids:
                    worksheet.write_string(line_index, i, ptav.attribute_id.name)
                    i += 1
                    worksheet.write_string(line_index, i, ptav.name)
                    i += 1
                i += (max_variant_values - len(product.product_template_variant_value_ids)) * 2
            values = product.mapped(FILE_COLUMNS[col])
            if col.startswith('variant_vendor_'):
                if values and values[seller_index]:
                    values_formated = values[seller_index]
                else:
                    values_formated = CustomExportUtility.manage_type_info(col)
            else:
                if len(values) > 1:
                    values_formated = ','.join(filter(lambda v: v, values))
                elif len(values) == 1:
                    values_formated = values[0] if values[0] else CustomExportUtility.manage_type_info(col)
                else:
                    values_formated = ""
            worksheet.write_string(line_index, i, str(values_formated))
            i += 1

    @staticmethod
    def manage_type_info(col):
        if TYPE_COLUMNS[col] == str:
            return ""
        elif TYPE_COLUMNS[col] == float:
            return 0
