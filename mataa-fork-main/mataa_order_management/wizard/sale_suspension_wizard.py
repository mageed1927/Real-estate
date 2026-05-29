from odoo import models, fields, api

class SaleSuspensionWizard(models.TransientModel):
    _name = 'sale.suspension.wizard'
    _description = 'Sale Order Suspension Wizard'

    sale_order_id = fields.Many2one('sale.order', string="Sale Order", required=True)
    suspension_reason = fields.Text(string="Suspension Reason", required=True)

    def action_confirm_suspension(self):
        self.ensure_one()
        order = self.sale_order_id
        order.is_suspended = not order.is_suspended
        new_note = f"Suspension reason: {self.suspension_reason}"
        if order.internal_note:
            order.internal_note = f"{order.internal_note}\n{new_note}"
        else:
            order.internal_note = new_note
        return {'type': 'ir.actions.act_window_close'}