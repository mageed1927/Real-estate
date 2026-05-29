# -*- coding: utf-8 -*-

from odoo import models, fields, api
import json

from odoo.exceptions import UserError
from ..services.tags_sync_service import TagSyncService
from ..data_models.tag_dto import TagDTO


class ProductTag(models.Model):
    _inherit = 'product.tag'

    mataa_id = fields.Char(string="Mataa ID", readonly=True)
    is_synced = fields.Boolean(string="Is Synced", default=False, readonly=True)

    @api.model
    def create(self, vals):
        if self.env.context.get('test_import'):
            return super(ProductTag, self).create(vals)

        if self.env.context.get('pre_sync'):
            return super(ProductTag, self).create(vals)

        created = super(ProductTag, self).create(vals)

        created.create_on_external()

        return created

    def write(self, vals):
        if self.env.context.get('test_import'):
            return super(ProductTag, self).write(vals)

        if self.env.context.get('pre_sync'):
            return super(ProductTag, self).write(vals)

        updated = super(ProductTag, self).write(vals)

        if self.is_synced and self.mataa_id:
            self.update_on_external()

        return updated

    def unlink(self):
        for record in self:
            try:
                if record.is_synced and record.mataa_id:
                    TagSyncService.delete(record.id)

                super(ProductTag, record).unlink()
            except Exception as e:
                raise UserError(f"Error deleting tag {record.id}: {str(e)}")
        return True

    def create_on_external(self):
        tag_dto = TagDTO.from_odoo(self)
        sync_result = TagSyncService.create(tag_dto['id'], tag_dto)

        external_id = sync_result.get('data', {}).get('id')

        self.write({
            'mataa_id': external_id,
            'is_synced': True
        })
        return self

    def update_on_external(self):
        tag_dto = TagDTO.from_odoo(self)
        sync_result = TagSyncService.update(tag_dto['id'], tag_dto)
        return self
