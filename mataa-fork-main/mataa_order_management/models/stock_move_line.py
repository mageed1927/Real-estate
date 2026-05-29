# -*- coding: utf-8 -*-

from odoo import api, fields, models


class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    mataa_vendor_name = fields.Char(
        compute='_compute_mataa_return_line_meta',
        string='Vendor Name',
        readonly=True,
    )
    mataa_is_inhouse_line = fields.Boolean(
        compute='_compute_mataa_return_line_meta',
        string='Is Inhouse Line',
        readonly=True,
    )

    def _get_mataa_sale_line(self):
        self.ensure_one()
        move = self.move_id
        sale_line = move.sale_line_id
        if sale_line:
            return sale_line

        candidate_moves = move.move_orig_ids | move.origin_returned_move_id
        visited = self.env['stock.move']
        while candidate_moves:
            next_moves = self.env['stock.move']
            for candidate_move in candidate_moves - visited:
                if candidate_move.sale_line_id:
                    return candidate_move.sale_line_id
                visited |= candidate_move
                next_moves |= candidate_move.move_orig_ids | candidate_move.origin_returned_move_id
            candidate_moves = next_moves - visited
        return False

    @api.depends(
        'move_id.sale_line_id.vendor_id',
        'move_id.sale_line_id.inhouse_location',
        'move_id.move_orig_ids.sale_line_id.vendor_id',
        'move_id.move_orig_ids.sale_line_id.inhouse_location',
        'move_id.origin_returned_move_id.sale_line_id.vendor_id',
        'move_id.origin_returned_move_id.sale_line_id.inhouse_location',
    )
    def _compute_mataa_return_line_meta(self):
        for line in self:
            sale_line = line._get_mataa_sale_line()
            line.mataa_vendor_name = sale_line.vendor_id.name if sale_line and sale_line.vendor_id else False
            line.mataa_is_inhouse_line = bool(sale_line and sale_line.inhouse_location)

    def _get_fields_stock_barcode(self):
        return super()._get_fields_stock_barcode() + [
            'mataa_vendor_name',
            'mataa_is_inhouse_line',
        ]
