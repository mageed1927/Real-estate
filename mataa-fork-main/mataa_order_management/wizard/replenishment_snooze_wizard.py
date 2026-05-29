# -*- coding: utf-8 -*-
from odoo import models, fields, api


class StockOrderpointSnooze(models.TransientModel):
    _inherit = 'stock.orderpoint.snooze'

    snooze_manual = fields.Boolean(string="Snooze Manually")

    @api.onchange('snooze_manual')
    def _onchange_snooze_manual(self):
        if self.snooze_manual:
            self.predefined_date = False
    def action_snooze(self):
        if self.snooze_manual:
            self.orderpoint_ids.write({
                'snoozed_until': False,
                'snooze_manual': True
            })
            return {'type': 'ir.actions.act_window_close'}

        res = super(StockOrderpointSnooze, self).action_snooze()
        self.orderpoint_ids.write({'snooze_manual': False})
        return res