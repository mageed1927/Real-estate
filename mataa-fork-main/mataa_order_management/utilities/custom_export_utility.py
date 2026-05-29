import os

import io
import xlsxwriter


class CustomExportUtility:

    @staticmethod
    def export_move_lines(move_lines):
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {"in_memory": True})
        worksheet = workbook.add_worksheet('')
        header_format = workbook.add_format({"bold": True})
        CustomExportUtility.create_header(worksheet, header_format)
        line_index = 1
        for move in move_lines:
            worksheet.write_string(line_index, 0, move.product_id.barcode, header_format)
            package_name = move.result_package_id.name if move.result_package_id else ''
            worksheet.write_string(line_index, 1, package_name, header_format)
            worksheet.write(line_index, 2, move.quantity, header_format)
            line_index += 1

        workbook.close()
        xlsx_data = output.getvalue()
        return xlsx_data

    @staticmethod
    def create_header(worksheet, header_format):
        worksheet.write_string(0, 0, 'product-variant-barcode', header_format)
        worksheet.write_string(0, 1, 'package-name', header_format)
        worksheet.write_string(0, 2, 'quantity', header_format)
