# -*- coding: utf-8 -*-
from odoo import models, fields, tools


class ComponentSaleReport(models.Model):
    _name = 'component.sale.report'
    _description = 'Component Sales Analysis'
    _auto = False

    order_date = fields.Datetime('Order Date', readonly=True)
    product_tmpl_id = fields.Many2one('product.template', 'Kit Product', readonly=True)
    component_product_id = fields.Many2one('product.product', 'Component', readonly=True)

    supplier_id = fields.Many2one(
        'res.partner',
        string='Vendor',
        readonly=True,
        domain=[('supplier', '=', True)]
    )

    qty_component = fields.Float('Component Quantity', readonly=True)
    qty_kit = fields.Float('Kit Quantity', readonly=True)
    price_total = fields.Float('Total Price', readonly=True)
    company_id = fields.Many2one('res.company', 'Company', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                SELECT
                    ROW_NUMBER() OVER () AS id,
                    so.date_order AS order_date,
                    pt.id AS product_tmpl_id,
                    mbl.product_id AS component_product_id,

                    (SELECT partner_id FROM product_supplierinfo WHERE product_id = mbl.product_id LIMIT 1) AS supplier_id,

                    (sol.product_uom_qty * mbl.product_qty) AS qty_component,
                    (sol.product_uom_qty / (SELECT count(id) FROM mrp_bom_line WHERE bom_id = bom.id)) AS qty_kit,
                    (sol.price_subtotal / (SELECT count(id) FROM mrp_bom_line WHERE bom_id = bom.id)) AS price_total,
                    sol.company_id AS company_id
                FROM
                    sale_order_line sol
                    JOIN sale_order so ON (so.id = sol.order_id)
                    JOIN product_product p ON (p.id = sol.product_id)
                    JOIN product_template pt ON (pt.id = p.product_tmpl_id)
                    JOIN mrp_bom bom ON (
                        bom.product_tmpl_id = pt.id 
                        AND bom.active = true 
                        AND (bom.company_id IS NULL OR bom.company_id = so.company_id)
                    )
                    JOIN mrp_bom_line mbl ON (mbl.bom_id = bom.id)
                    LEFT JOIN product_product comp_p ON (comp_p.id = mbl.product_id)
                    LEFT JOIN product_template comp_pt ON (comp_pt.id = comp_p.product_tmpl_id)
                WHERE
                    so.state IN ('sale', 'done')
                    AND pt.detailed_type = 'consu'
                    AND (SELECT count(id) FROM mrp_bom_line WHERE bom_id = bom.id) > 0
            )
        """ % (self._table,))