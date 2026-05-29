from odoo import models, fields, api
from odoo.exceptions import UserError
from ..data_models.attribute_value_dto import AttributeValueDTO
from ..services.attribute_value_sync_service import AttributeValueSyncService

import json


class AttributeValue(models.Model):
    _inherit = 'product.attribute.value'

    mataa_id = fields.Char(string="Mataa ID", readonly=True)
    is_synced = fields.Boolean(string="Is Synced", default=False, readonly=True)

    @api.model
    def create(self, vals):
        if self.env.context.get('test_import'):
            return super(AttributeValue, self).create(vals)

        if self.env.context.get('pre_sync'):
            return super(AttributeValue, self).create(vals)

        created = super(AttributeValue, self).create(vals)

        created.create_on_external()

        return created

    def write(self, vals):
        if self.env.context.get('test_import'):
            return super(AttributeValue, self).write(vals)

        if self.env.context.get('pre_sync'):
            return super(AttributeValue, self).write(vals)

        updated = super(AttributeValue, self).write(vals)

        for record in self:
            if record.is_synced and record.mataa_id:
                record.update_on_external()

        return updated

    def unlink(self):
        for record in self:
            try:
                if record.is_synced and record.mataa_id:
                    AttributeValueSyncService.delete(record.id)

                super(AttributeValue, record).unlink()
            except Exception as e:
                raise UserError(f"Error deleting attribute-value {record.id}: {str(e)}")
        return True

    def create_on_external(self):
        attribute_value_dto = AttributeValueDTO.from_odoo(self)
        sync_result = AttributeValueSyncService.create(attribute_value_dto)

        external_id = sync_result.get('data', {}).get('id')

        self.write({
            'mataa_id': external_id,
            'is_synced': True
        })
        return self

    def update_on_external(self):
        attribute_value_dto = AttributeValueDTO.from_odoo(self)
        sync_result = AttributeValueSyncService.update(attribute_value_dto['id'], attribute_value_dto)
        return self
