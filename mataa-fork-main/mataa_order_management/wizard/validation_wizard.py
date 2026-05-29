from odoo import models, fields, _
from odoo.exceptions import UserError


class PickingValidatePrintWizard(models.TransientModel):
    _name = "picking.validate.print.wizard"
    _description = "Confirm delivery note printing before validation"

    message = fields.Text(
        default=lambda self: _(
            "A delivery note will be printed before validation.\n"
            "Do you want to continue?"
        )
    )

    def action_print_and_validate(self):
        self.ensure_one()
        picking = self.env['stock.picking'].browse(self.env.context.get('active_id'))

        print_action = picking.action_print_out_picking_report()

        picking.with_context(skip_pack_validate_wizard=True).button_validate()

        if print_action:
            print_action['close_on_report_download'] = True
            return print_action

        return {'type': 'ir.actions.act_window_close'}