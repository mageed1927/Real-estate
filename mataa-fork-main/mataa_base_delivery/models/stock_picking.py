# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class StockPicking(models.Model):
    _inherit = "stock.picking"

    def get_carrier_state(self, status):
        # statuses: out_partially_delivered, out_delivered, out_returned
        self.ensure_one()
        carrier_id = self.carrier_id
        if self.carrier_id:
            if hasattr(carrier_id, 'get_%s_shipment_status' % carrier_id.delivery_type):
                status = getattr(carrier_id, 'get_%s_shipment_status' % carrier_id.delivery_type)(self, status)
        return status