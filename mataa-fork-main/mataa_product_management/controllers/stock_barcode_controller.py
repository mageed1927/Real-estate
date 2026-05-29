from odoo import api, fields, models
from odoo.addons.stock_barcode.controllers.stock_barcode import StockBarcodeController

from odoo.http import request


class NewModule(StockBarcodeController):

    def _get_groups_data(self):
        res = super()._get_groups_data()
        res.update({
            'group_edit_lines_barcodes': request.env.user.has_group('mataa_product_management.group_edit_lines_barcodes'),
        })
        return res
