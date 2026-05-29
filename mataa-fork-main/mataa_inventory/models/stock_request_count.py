# -*- coding: utf-8 -*-
from odoo import models, fields

class StockRequestCount(models.TransientModel):
    _inherit = 'stock.request.count'

    def action_request_count(self):
        res = super(StockRequestCount, self).action_request_count()
        active_ids = self.env.context.get('active_ids')
        if active_ids:
            quants = self.env['stock.quant'].browse(active_ids)

            quants.write({
                'assigned_by': self.env.user.id
                })

        return res