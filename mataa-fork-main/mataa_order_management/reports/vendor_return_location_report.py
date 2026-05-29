# -*- coding: utf-8 -*-
from odoo import models, fields, tools, _
from odoo.exceptions import UserError

class VendorReturnLocationReport(models.Model):
    _name = "vendor.return.location.report"
    _description = "Vendors and Products at Return Location"
    _auto = False
    _order = 'quantity desc'

    product_id = fields.Many2one('product.product', string='Product', readonly=True)
    vendor_id = fields.Many2one('res.partner', string='Vendor', readonly=True)
    sale_order_id = fields.Many2one('sale.order', string='Sales Order', readonly=True)
    purchase_order_id = fields.Many2one('purchase.order', string='Purchase Order', readonly=True)
    quantity = fields.Float('Quantity', readonly=True)

    def create_vendor_return_batch(self):
        if not self:
            raise UserError(_("Please select at least one product line."))

        StockPicking = self.env['stock.picking']
        StockPickingBatch = self.env['stock.picking.batch']

        created_pickings = set()

        for line in self:
            po = line.purchase_order_id
            product = line.product_id

            if not po:
                raise UserError(_("No Purchase Order found for product %s.") % product.display_name)

            # Get the validated incoming pickings for this PO
            incoming_pickings = StockPicking.search([
                ('purchase_id', '=', po.id),
                ('picking_type_code', '=', 'incoming'),
                ('state', '=', 'done'),
            ])

            if not incoming_pickings:
                raise UserError(_("No completed receipt found for PO %s.") % po.name)

            picking_to_return = incoming_pickings[-1]

            return_wizard = self.env['stock.return.picking'].with_context(
                active_id=picking_to_return.id,
                active_ids=[picking_to_return.id],
                active_model='stock.picking'
            ).create({})

            for rline in return_wizard.product_return_moves:
                if rline.product_id != product:
                    rline.unlink()

            return_line = return_wizard.product_return_moves
            if not return_line:
                raise UserError(_("Product %s not found in picking %s.") %
                                (product.display_name, picking_to_return.name))

            return_line.quantity = line.quantity

            result = return_wizard.create_returns()
            return_picking = StockPicking.browse(result.get('res_id'))
            return_location = self.env['stock.location'].search([
                ('complete_name', '=', 'WH/Stock/Return')
            ], limit=1)
            if not return_location:
                raise UserError(_("Return location 'WH/Stock/Return' not found. Please check configuration."))

            return_picking.write({'location_id': return_location.id})

            return_picking.move_ids.write({'location_id': return_location.id})
            return_picking.move_line_ids.write({'location_id': return_location.id})

            created_pickings.add(return_picking.id)

        if not created_pickings:
            raise UserError(_("No return pickings were created."))

        vendors = list(set(line.vendor_id.id for line in self if line.vendor_id))
        vendor_id = vendors[0] if len(vendors) == 1 else False  # assign only if all lines share one vendor
        first_picking = self.env['stock.picking'].browse(next(iter(created_pickings)))
        batch_vals = {
            # 'name': _('Vendor Return Batch'),
            'picking_type_id': first_picking.picking_type_id.id,
            'picking_ids': [(6, 0, list(created_pickings))],
        }
        if 'vendor_id' in StockPickingBatch._fields:
            batch_vals['vendor_id'] = vendor_id
        elif 'partner_id' in StockPickingBatch._fields:
            batch_vals['partner_id'] = vendor_id

        batch = StockPickingBatch.create(batch_vals)

        for picking in batch.picking_ids:
            picking.action_confirm()
            picking.action_assign()
            for move in picking.move_ids:
                if not move.move_line_ids:
                    self.env['stock.move.line'].create({
                        'move_id': move.id,
                        'picking_id': picking.id,
                        'product_id': move.product_id.id,
                        'product_uom_id': move.product_uom.id,
                        'qty_done': move.product_uom_qty,
                        'location_id': move.location_id.id,
                        'location_dest_id': move.location_dest_id.id,
                    })
                else:
                    move.move_line_ids.write({'qty_done': move.product_uom_qty})

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking.batch',
            'view_mode': 'form',
            'res_id': batch.id,
            'target': 'current',
        }

    def init(self):
        self.env.cr.execute("""
            DO $$
            BEGIN
                IF EXISTS (SELECT 1 FROM information_schema.views WHERE table_name = 'vendor_return_location_report') THEN
                    EXECUTE 'DROP VIEW vendor_return_location_report CASCADE';
                ELSIF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'vendor_return_location_report') THEN
                    EXECUTE 'DROP TABLE vendor_return_location_report CASCADE';
                END IF;
            END$$;
        """)

        # 1. Identify the Return Location ID
        self.env.cr.execute("""
            SELECT id FROM stock_location
            WHERE complete_name = 'WH/Stock/Return'
            LIMIT 1;
        """)
        row = self.env.cr.fetchone()
        if not row:
            tools.drop_view_if_exists(self.env.cr, self._table)
            self.env.cr.execute(f"CREATE OR REPLACE VIEW {self._table} AS (SELECT 1 AS id WHERE false);")
            return
        return_location_id = row[0]

        # 2. Build the query requiring a linked Sale Order
        query = f"""
            CREATE OR REPLACE VIEW {self._table} AS (
                WITH return_quants AS (
                    /* Current physical stock in the return location */
                    SELECT
                        q.product_id,
                        SUM(q.quantity) AS total_qty
                    FROM stock_quant q
                    WHERE q.location_id = {return_location_id}
                      AND q.quantity > 0
                    GROUP BY q.product_id
                ),
                latest_purchase_with_so AS (
                    /* Find the most recent purchase data that HAS a linked Sale Order */
                    SELECT 
                        pol.product_id,
                        po.partner_id AS vendor_id,
                        po.id AS purchase_order_id,
                        po.sale_order_id,
                        ROW_NUMBER() OVER(PARTITION BY pol.product_id ORDER BY po.date_order DESC) as rank
                    FROM purchase_order_line pol
                    JOIN purchase_order po ON po.id = pol.order_id
                    WHERE po.state NOT IN ('draft', 'cancel')
                      AND po.sale_order_id IS NOT NULL  /* Ensure SO link exists */
                )
                SELECT
                    ROW_NUMBER() OVER() AS id,
                    rq.product_id,
                    lp.vendor_id,
                    lp.sale_order_id,
                    lp.purchase_order_id,
                    rq.total_qty AS quantity
                FROM return_quants rq
                INNER JOIN latest_purchase_with_so lp 
                    ON lp.product_id = rq.product_id 
                    AND lp.rank = 1
                /* INNER JOIN ensures that if no ranked purchase with an SO is found, 
                   the product is excluded entirely */
            );
        """
        self.env.cr.execute(query)