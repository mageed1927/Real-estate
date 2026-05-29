# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class OrderCancelWizard(models.TransientModel):
    _name = 'order.cancel.wizard'
    _description = 'Order Cancellation Wizard'

    order_ids = fields.Many2many('sale.order', string='Orders')

    reason_ids = fields.Many2many(
        'order.cancel.reason',
        string='Cancellation Reasons',
        required=True,
    )

    note = fields.Text(string='Description / Note')

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_model = self._context.get('active_model')
        active_ids = self._context.get('active_ids')
        if active_model == 'sale.order' and active_ids:
            res['order_ids'] = [(6, 0, active_ids)]
        return res

    def action_confirm_cancel(self):
        self.ensure_one()
        if not self.reason_ids:
            raise UserError(_("Please select at least one cancellation reason."))

        for order in self.order_ids:
            # Save cause on the order
            order.write({
                'cancel_reason_ids': [(6, 0, self.reason_ids.ids)],
                'cancel_note': self.note,
            })

            # Call your normal cancel logic
            order._action_cancel()

        return {'type': 'ir.actions.act_window_close'}
