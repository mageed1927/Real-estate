from odoo import models, fields, api
from odoo.exceptions import UserError
from ..services.attribute_entity_state_service import AttributeEntityStateSyncService
import json


class Attribute(models.Model):
    _inherit = 'product.attribute'

    mataa_id = fields.Char(string="Mataa ID", readonly=True)
    is_synced = fields.Boolean(string="Is Synced", default=False, readonly=True)

    app_entity_state = fields.Selection(
        selection=[('1', 'Active'), ('2', 'Inactive')],
        string='App Entity State',
        default='1',
        required=True,
    )

    @api.model
    def create(self, vals):
        if self.env.context.get('test_import'):
            return super(Attribute, self).create(vals)

        if self.env.context.get('pre_sync'):
            return super(Attribute, self).create(vals)

        created = super(Attribute, self).create(vals)

        return created

    def write(self, vals):
        if self.env.context.get('test_import'):
            return super(Attribute, self).write(vals)

        if self.env.context.get('pre_sync'):
            return super(Attribute, self).write(vals)

        updated = super(Attribute, self).write(vals)
        if not self.env.context.get('mataa_skip_external_sync') and 'visibility' in vals:
            for attr in self:
                AttributeEntityStateSyncService.update_state_by_odoo_id(attr.name, attr.visibility)

        # update all values (to resolve change of name issue)
        for attribute in self:
            attribute.value_ids.write({})

        return updated

    def unlink(self):
        for record in self:
            try:
                # delete all values
                record.value_ids.unlink()

                super(Attribute, record).unlink()
            except Exception as e:
                raise UserError(f"Error deleting attribute {record.id}: {str(e)}")
        return True
    