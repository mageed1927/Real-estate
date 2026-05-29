# -*- coding: utf-8 -*-
from odoo import api, fields, models


class StockPickingBatch(models.Model):
    _inherit = 'stock.picking.batch'

    def _get_stock_barcode_data(self):
        picking_data = super()._get_stock_barcode_data()

        if self:
            for batch in picking_data['records'].get(self._name, []):
                batch_rec = self.browse(batch['id'])
                carrier_name = (batch_rec.carrier_id.name or '').lower()
                batch_name = (batch_rec.name or '').lower()
                batch['scan_by_transfer'] = batch_name.startswith('camex') or carrier_name == 'camex'

        return picking_data


    @api.model
    def camex_fill_quantities(self, picking_ids):
        if not picking_ids:
            return False

        pickings = self.env["stock.picking"].browse(picking_ids)
        updated_count = 0

        for picking in pickings:
            for line in picking.move_line_ids:
                if "product_uom_qty" in line._fields:
                    target_qty = line.product_uom_qty
                elif "quantity" in line._fields:
                    target_qty = line.quantity
                elif "reserved_qty" in line._fields:
                    target_qty = line.reserved_qty
                elif "reserved_availability" in line._fields:
                    target_qty = line.reserved_availability
                else:
                    target_qty = line.move_id.product_uom_qty

                if target_qty and line.qty_done != target_qty:
                    line.qty_done = target_qty
                    updated_count += 1

        return updated_count

    @api.model
    def camex_get_barcode_data(self, batch_id):
        batch = self.browse(batch_id)
        return batch._get_stock_barcode_data()

    def action_done(self):
        res = super().action_done()

        for batch in self:
            sale_orders = batch.picking_ids.mapped("sale_id")
            if sale_orders:
                sale_orders.write({"mata_order_state": "shipping"})

        return res