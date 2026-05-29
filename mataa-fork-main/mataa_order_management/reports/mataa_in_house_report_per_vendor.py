# -*- coding: utf-8 -*-

from odoo import models, fields, api, _, tools
import odoo.addons.decimal_precision as dp
from odoo import tools
from datetime import datetime, date


class MataaInHouseReportPerVendor(models.Model):
    _name = "mataa.in.house.report.per.vendor"
    _description = "Mataa In House Report Per Vendor"
    _auto = False
    _order = 'on_hand_qty desc'

    # Product
    name = fields.Char('Product Name')
    vendor_id = fields.Many2one('res.partner', 'Vendor')
    product_id = fields.Many2one('product.product', 'Product')
    min_qty = fields.Float('Vendor Qty')
    price = fields.Float('Price')

    vendor_product_name = fields.Char('Vendor Product Name')
    vendor_product_code = fields.Char('Vendor Product Code')

    categ_id = fields.Many2one('product.category', 'Product Category')
    uom_id = fields.Many2one('uom.uom', 'UoM')
    product_brand_id = fields.Many2one("product.brand", string="Brand")

    mataa_id = fields.Char('Mataa ID')
    default_code = fields.Char('Internal Reference')
    barcode = fields.Char('Barcode')

    on_hand_qty = fields.Float('On Hand')

    @api.model
    def get_columns(self):
        columns = {
            # Product
            'id': 'psi.id',
            'vendor_id': 'psi.partner_id',
            'product_id': 'psi.product_id',
            'min_qty': 'psi.min_qty',
            'price': 'psi.price',
            'vendor_product_code': 'psi.product_code',
            'vendor_product_name': 'psi.product_name',

            'name': 'pt.name',
            'categ_id': 'pt.categ_id',
            'uom_id': 'pt.uom_id',
            'product_brand_id': 'pt.product_brand_id',
            'mataa_id': 'pp.mataa_id',
            'default_code': 'pp.default_code',
            'barcode': 'pp.barcode',

            'on_hand_qty': 'sum(sq.quantity)',

        }

        return columns

    @api.model
    def get_tables(self):
        location_ids = tuple(self.env.company.mataa_in_stock_locations_ids.ids)

        # Ensure the SQL query does not break when location_ids is empty
        location_condition = f"AND sq.location_id in {location_ids}" if location_ids else ""

        dic = {
            'psi': ['', 'product_supplierinfo %s', ''],
            'pp': ['left join', 'product_product %s', 'on pp.id = psi.product_id'],
            'pt': ['left join', 'product_template %s', 'on pt.id = psi.product_tmpl_id'],
            'sq': ['left join', 'stock_quant %s', f'on sq.product_id = psi.product_id {location_condition}'],
        }

        return dic

    @api.model
    def get_where_clause(self):
        return {}


    @api.model
    def select(self):
        columns = ', '.join(['%s %s' % (v, k) for k, v in self.get_columns().items()])
        tables = ' '.join(['%s %s %s' % tuple(v) % k for k, v in self.get_tables().items()])
        where_clause = ' and '.join(self.get_where_clause().values())
        where_clause = where_clause and 'where %s' % where_clause

        project_select = f"""
        select {columns}
        from {tables}
        {where_clause}
        group by psi.id, psi.partner_id, psi.product_id, psi.min_qty, psi.price, psi.product_code, psi.product_name, pt.name, pt.categ_id, pt.uom_id, pt.product_brand_id, pp.mataa_id, pp.default_code, pp.barcode
        """
        query = """
        CREATE or REPLACE VIEW {view_name} as (
        {project_select}
        ); 
        """.format(**locals(), view_name=self._table)
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(query)

    def init(self):
        self.select()
