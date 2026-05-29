# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    is_pack_operation = fields.Boolean(
        string="Is a PACK Operation?",
        compute='_compute_is_pack_operation',
        store=True
    )

    @api.depends('picking_type_id.name')
    def _compute_is_pack_operation(self):
        for picking in self:
            # "PACK" only
            if picking.picking_type_id.name and picking.picking_type_id.name.strip().lower() == 'pack':
                picking.is_pack_operation = True
            else:
                picking.is_pack_operation = False

    def action_print_out_picking_report(self):
        """
        This function is for the second button (Draft Print)
        and it prints the custom report.
        """
        self.ensure_one()
        out_picking = self.move_ids.move_dest_ids.picking_id
        if not out_picking:
            raise UserError("لم يتم العثور على حركة التسليم (OUT) المرتبطة.")

        return self.env.ref('mataa_order_management.action_report_picking_draft').report_action(out_picking)

    # TODO : this is a temporary fix
    def action_print_out_picking_report_final(self):
        return self.action_print_out_picking_report()

    # def action_print_out_picking_report_final(self):
    #     """
    #     This new function is for the first button (Original Print)
    #     and it prints the default Odoo report.
    #     """
    #     self.ensure_one()
    #     out_picking = self.move_ids.move_dest_ids.picking_id
    #     if not out_picking:
    #         raise UserError("لم يتم العثور على حركة التسليم (OUT) المرتبطة.")
    #
    #     # Call the default Odoo report action
    #     return self.env.ref('stock.action_report_picking').report_action(out_picking)