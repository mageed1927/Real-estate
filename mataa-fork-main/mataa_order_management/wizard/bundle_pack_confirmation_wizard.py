# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError

class BundlePackConfirmationWizard(models.TransientModel):
    _name = 'bundle.pack.confirmation.wizard'
    _description = 'Bundle Pack Confirmation Wizard'

    msg = fields.Char('Confirmation Message', required=True, readonly=True)
    pack_picking_id = fields.Many2one('stock.picking', required=True, readonly=True)

    def validate_all_packs(self):
        picking = self.pack_picking_id
        ctx = dict(self.env.context, skip_bundle_pack_confirmation=True)

        if picking.carrier_id and picking.carrier_id.delivery_type == 'dms':
            ctx['skip_pack_validate_wizard'] = True

        return picking.with_context(**ctx).button_validate()