# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import UserError
from ..data_models.partner_dto import PartnerDTO
from ..services.res_partner_sync_service import ResPartnerSyncService

import json


class ResPartner(models.Model):
    _inherit = 'res.partner'

    mataa_id = fields.Char(string="Mataa ID", readonly=True)
    is_synced = fields.Boolean(string="Is Synced", default=False, readonly=True)

    @api.model_create_multi
    def create(self, vals):
        if self.env.context.get('test_import'):
            return super(ResPartner, self).create(vals)

        if self.env.context.get('pre_sync'):
            return super(ResPartner, self).create(vals)

        partner_ids = super(ResPartner, self.with_context(skip_update_sync=True)).create(vals)
        partner_ids.sync_to_external()

        return partner_ids

    def write(self, vals):
        if self.env.context.get('test_import') or self.env.context.get('pre_sync'):
            return super(ResPartner, self).write(vals)

        updated = super(ResPartner, self).write(vals)
        if not self._context.get('skip_update_sync', False):
            self.sync_to_external(update=True)

        return updated

    def unlink(self):
        for record in self:
            try:
                if record.is_synced and record.mataa_id:
                    ResPartnerSyncService.delete(record.id, env=self.env)
                super(ResPartner, record).unlink()
            except Exception as e:
                raise UserError(f"Error deleting customer {record.id}: {str(e)}")
        return True

    def sync_to_external(self, update=False):
        # Filter out vendors (supplier_rank > 0) and non-customers (customer_rank == 0), only individuals
        customers = self.filtered(lambda p: p.customer_rank > 0 and p.supplier_rank == 0 and not p.is_company)
        for customer in customers:

            dto = PartnerDTO.from_odoo(customer)
            service = ResPartnerSyncService

            if update:
                service.update(customer.id, dto, env=self.env)
            else:
                result = service.create(dto, env=self.env)
                external_id = result.get('data', {}).get('id')

                if external_id:
                    customer.write({
                        'mataa_id': external_id,
                        'is_synced': True,
                    })
                else:
                    if external_id:
                        customer.write({
                            'is_synced': True,
                        })
