from odoo import http
from odoo.http import content_disposition, request

from datetime import datetime
from ..utility.import_variants_error_file_generator import \
    ImportVariantsErrorFileGenerator


class ExportErrorFilesController(http.Controller):

    @http.route(['/download/error_files'], type='http', auth="user")
    def export_error_files(self, column_names, failed_rows):
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S%f')[:-3]
        column_names = [str(column) for column in column_names.split(',')]
        file_data = ImportVariantsErrorFileGenerator.generate_file_data(column_names, failed_rows)
        return request.make_response(file_data, headers=[
            ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
            ('Content-Disposition', content_disposition(f"failed_imports_{timestamp}.xlsx"))])
