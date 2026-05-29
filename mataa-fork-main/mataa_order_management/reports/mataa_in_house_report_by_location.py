# -*- coding: utf-8 -*-

from odoo import models, fields, api, _, tools
import odoo.addons.decimal_precision as dp
from odoo import tools
from datetime import datetime, date


class MataaInHouseReport(models.Model):
    _name = "mataa.in.house.report"
    _description = "Mataa In House Report"
    _auto = False
    _order = 'on_hand_qty desc'

    # Product
    name = fields.Char('Product Name')
    product_id = fields.Many2one('product.product', 'Product')
    categ_id = fields.Many2one('product.category', 'Product Category')
    uom_id = fields.Many2one('uom.uom', 'UoM')
    product_brand_id = fields.Many2one("product.brand", string="Brand")
    location_id = fields.Many2one('stock.location', 'Location')

    mataa_id = fields.Char('Mataa ID')
    default_code = fields.Char('Internal Reference')
    barcode = fields.Char('Barcode')

    was_in_house = fields.Boolean()

    on_hand_qty = fields.Float('On Hand')

    @api.model
    def get_columns(self):
        columns = {
            # Product
            'id': 'pp.id',
            'product_id': 'pp.id',
            'was_in_house': 'pp.was_in_house',
            'name': 'pt.name',
            'categ_id': 'pt.categ_id',
            'uom_id': 'pt.uom_id',
            'mataa_id': 'pp.mataa_id',
            'default_code': 'pp.default_code',
            'barcode': 'pp.barcode',
            'product_brand_id': 'pt.product_brand_id',

            'location_id': 'sq.location_id',
            'on_hand_qty': 'sq.quantity',

        }

        return columns

    @api.model
    def get_tables(self):
        location_ids = tuple(self.env.company.mataa_in_stock_locations_ids.ids)

        # Ensure the SQL query does not break when location_ids is empty
        location_condition = f"AND sq.location_id in {location_ids}" if location_ids else ""

        dic = {
            'pp': ['', 'product_product %s', ''],
            'pt': ['left join', 'product_template %s', 'on pt.id = pp.product_tmpl_id'],
            'sq': ['left join', 'stock_quant %s', f'on sq.product_id = pp.id {location_condition}'],
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
