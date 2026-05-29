# -*- coding: utf-8 -*-

from odoo import models, fields, api
import json

from odoo.exceptions import UserError
from ..services.category_sync_service import CategorySyncService
from ..data_models.category_dto import CategoryDTO


class ProductPublicCategory(models.Model):
    _inherit = 'product.public.category'

    mataa_id = fields.Char(string="Mataa ID", readonly=True)
    is_synced = fields.Boolean(string="Is Synced", default=False, readonly=True)

    mataa_slug = fields.Char("Mataa Slug")
    active = fields.Boolean(string="Active", default=True)

    @api.model
    def create(self, vals):
        if self.env.context.get('test_import'):
            return super(ProductPublicCategory, self).create(vals)

        if self.env.context.get('pre_sync'):
            return super(ProductPublicCategory, self).create(vals)

        created = super(ProductPublicCategory, self).create(vals)

        created.create_on_external()

        return created

    def write(self, vals):
        if self.env.context.get('test_import'):
            return super(ProductPublicCategory, self).write(vals)

        if self.env.context.get('pre_sync'):
            return super(ProductPublicCategory, self).write(vals)

        updated = super(ProductPublicCategory, self).write(vals)

        for record in self:
            # skip sync is used to avoid sending children names that are updated from the parent category
            if record.is_synced and record.mataa_id and not self.env.context.get('skip_sync'):
                record.update_on_external()

        return updated

    def toggle_active(self):
        result = super(ProductPublicCategory, self).toggle_active()

        for record in self:
            if record.is_synced and record.mataa_id:
                record.update_on_external()

        return result


    def unlink(self):
        for record in self:
            try:
                if record.is_synced and record.mataa_id:
                    CategorySyncService.delete(record.id)

                super(ProductPublicCategory, record).unlink()
            except Exception as e:
                raise UserError(f"Error deleting category {record.mataa_id}: {str(e)}")
        return True


    def create_on_external(self):
        category_dto = CategoryDTO.from_odoo(self)
        sync_result = CategorySyncService.create(category_dto)

        external_id = sync_result.get('data', {}).get('id')

        self.write({
            'mataa_id': external_id,
            'is_synced': True
        })
        return self


    def update_on_external(self):
        category_dto = CategoryDTO.from_odoo(self)
        sync_result = CategorySyncService.update(category_dto['id'], category_dto)
        return self
