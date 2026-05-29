from odoo import http
from odoo.http import content_disposition, request

from ..utilities.custom_export_utility import CustomExportUtility


class ExportMoveLinesController(http.Controller):

    @http.route('/export/sml/<string:stock_move_line_ids>', type='http', auth="user")
    def export_products(self, stock_move_line_ids):
        stock_move_lines = request.env['stock.move.line'].browse(eval(stock_move_line_ids))
        xlsx_data = CustomExportUtility.export_move_lines(stock_move_lines)
        return request.make_response(xlsx_data, headers=[
            ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
            ('Content-Disposition', content_disposition('Move lines.xlsx'))])
