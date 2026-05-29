# -*- coding: utf-8 -*-

from odoo import models, fields, api
import json

from odoo.exceptions import UserError
from ..services.brand_sync_service import BrandSyncService
from ..data_models.brand_dto import BrandDTO


class ProductBrand(models.Model):
    _inherit = 'product.brand'

    mataa_id = fields.Char(string="Mataa ID", readonly=True)
    is_synced = fields.Boolean(string="Is Synced", default=False, readonly=True)

    @api.model
    def create(self, vals):
        if self.env.context.get('test_import'):
            return super(ProductBrand, self).create(vals)

        if self.env.context.get('pre_sync'):
            return super(ProductBrand, self).create(vals)

        created = super(ProductBrand, self).create(vals)

        created.create_on_external()

        return created

    def write(self, vals):
        if self.env.context.get('test_import'):
            return super(ProductBrand, self).write(vals)

        if self.env.context.get('pre_sync'):
            return super(ProductBrand, self).write(vals)

        updated = super(ProductBrand, self).write(vals)

        self.update_on_external()

        return updated

    def unlink(self):
        for record in self:
            try:
                if record.is_synced and record.mataa_id:
                    BrandSyncService.delete(record.id)

                super(ProductBrand, record).unlink()
            except Exception as e:
                raise UserError(f"Error deleting brand {record.id}: {str(e)}")
        return True

    def create_on_external(self):
        brand_dto = BrandDTO.from_odoo(self)
        sync_result = BrandSyncService.create(brand_dto)

        external_id = sync_result.get('data', {}).get('id')

        self.write({
            'mataa_id': external_id,
            'is_synced': True
        })
        return self

    def update_on_external(self):
        brand_dto = BrandDTO.from_odoo(self)
        sync_result = BrandSyncService.update(brand_dto['id'], brand_dto)
        return self
