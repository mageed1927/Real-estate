from odoo import models, fields, api

class ChoosePackageWizard(models.TransientModel):
    _name = "choose.package.wizard"
    _description = "Select Destination Package"

    picking_id = fields.Many2one("stock.picking", required=True)
    package_id = fields.Many2one("stock.quant.package", string="Destination Package", required=True)

    def apply(self):
        picking = self.picking_id

        for move_line in picking.move_line_ids:
            move_line.result_package_id = self.package_id

        return {'type': 'ir.actions.act_window_close'}
