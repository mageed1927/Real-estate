from odoo import models, fields, api, _
from odoo.exceptions import UserError


class StockQuantRelocate(models.TransientModel):
    _inherit = 'stock.quant.relocate'

    is_single_quant = fields.Boolean(compute='_compute_is_single_quant')
    moved_qty = fields.Float(string='Moved Quantity')

    def action_relocate_quants(self):
        self.ensure_one()

        if len(self.quant_ids) != 1:
            return super().action_relocate_quants()

        if self.moved_qty <= 0:
            raise UserError(_('Please enter a quantity greater than zero.'))

        if not self.dest_location_id:
            raise UserError(_('Please choose a destination location'))

        self.quant_ids.action_clear_inventory_quantity()
        quant = self.quant_ids[0]
        available_qty = quant.quantity - quant.reserved_quantity
        if self.moved_qty > available_qty:
            raise UserError(
                _(
                    'Requested quantity %(requested)s for %(product)s is greater than available quantity %(available)s.',
                    requested=self.moved_qty,
                    product=quant.product_id.display_name,
                    available=available_qty,
                )
            )

        move_vals = quant.with_context(inventory_name=self.message or _('Quantity Relocated'))._get_inventory_move_values(
            self.moved_qty,
            quant.location_id,
            self.dest_location_id or quant.location_id,
            quant.package_id,
            self.dest_package_id or False,
        )
        move = self.env['stock.move'].create(move_vals)
        move._action_done()

        lot_ids = self.quant_ids.lot_id
        product_ids = self.quant_ids.product_id
        if self.env.context.get('default_lot_id', False) and len(lot_ids) == 1:
            return lot_ids.action_lot_open_quants()
        if self.env.context.get('single_product', False) and len(product_ids) == 1:
            return product_ids.action_update_quantity_on_hand()

        return self.env['ir.actions.server']._for_xml_id(
            self.env.context.get('action_ref', 'stock.action_view_quants')
        )

    @api.depends('quant_ids')
    def _compute_is_single_quant(self):
        for record in self:
            record.is_single_quant = len(record.quant_ids) == 1
