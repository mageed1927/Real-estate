from odoo import http
from odoo.http import content_disposition, request
from ..utility.custom_export_utility import CustomExportUtility


class ExportProductsController(http.Controller):

    @http.route('/export/products/<string:product_ids>', type='http', auth="user")
    def export_products(self, product_ids):
        products = request.env['product.product'].browse(eval(product_ids))
        xlsx_data = CustomExportUtility.export_products(products)
        return request.make_response(xlsx_data, headers=[
            ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
            ('Content-Disposition', content_disposition('Products.xlsx'))])
