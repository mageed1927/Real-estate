from collections import defaultdict

import json

from odoo.exceptions import UserError
from ..data_models.variant_dto import VariantDTO
from ..services.variant_sync_service import VariantSyncService
from odoo import models, fields, api


class ProductProduct(models.Model):
    _inherit = 'product.product'

    mataa_id = fields.Char(string="Mataa ID")

    # TODO : this needs fixing and mapping after new product-catalog system integration
    mataa_status = fields.Selection([
        ('unspecified', 'Unspecified'),
        ('draft', 'draft'),
        ('publish', 'Published'),
    ], string='Status', default='publish')

    is_synced = fields.Boolean(string="Is Synced", default=False, tracking=True)
    synced_date = fields.Datetime(string="Synced Date", store=True, readonly=True)
    last_synced_quantity = fields.Float(string="Last Synced Quantity", default=0.0)
    sync_status = fields.Selection([
        ('not_synced', 'Not synced'),
        ('to_be_synced', 'To be synced'),
        ('synced', 'Synced')], string="Sync Status", default='not_synced')

    def set_sync_status(self):
        """Set sync status for old records"""
        for record in self:
            if record.is_synced and record.mataa_id:
                record.with_context(init_sync_status=True).sync_status = 'synced'
            else:
                record.with_context(init_sync_status=True).sync_status = 'not_synced'

    def get_mataa_quantity(self):
        self.ensure_one()

        supplier_list_quantity = sum(seller.min_qty for seller in self.seller_ids if seller.product_id.id == self.id
                                     and seller.published)
        product_quantity = supplier_list_quantity + self.get_free_qty()

        return product_quantity

    @api.model
    def create(self, vals):
        if self.env.context.get('test_import'):
            return super(ProductProduct, self).create(vals)

        if self.env.context.get('pre_sync'):
            created = super(ProductProduct, self).create(vals)
            if created.product_tmpl_id.mataa_id:
                created.mataa_status = 'publish'
            return created

        created = super(ProductProduct, self).create(vals)

        if created.product_tmpl_id.mataa_id:
            created.create_on_external()

        return created

    def write(self, vals):
        disable_async_sync = bool(
            self.env['ir.config_parameter'].sudo().get_param('mataa_external_sync.asynchronous_sync'))

        if 'is_synced' in vals and vals['is_synced']:
            now = fields.Datetime.now()
            for rec in self:
                rec.synced_date = now


        if self.env.context.get('test_import'):
            return super(ProductProduct, self).write(vals)

        if self.env.context.get('pre_sync'):
            return super(ProductProduct, self).write(vals)

        updated = super(ProductProduct, self).write(vals)

        for record in self:
            if record.mataa_id:
                if not disable_async_sync:
                    record.update_on_external()
                else:
                    if not self.env.context.get('init_sync_status', False) and record.sync_status != 'to_be_synced':
                        record.mark_for_sync()
        return updated

    def unlink(self):
        for record in self:
            try:
                if record.is_synced and record.mataa_id:
                    VariantSyncService.delete(record.id, env=self.env)

                super(ProductProduct, record).unlink()
            except Exception as e:
                raise UserError(f"Error deleting variant {record.id}: {str(e)}")
        return True

    def sync_variants(self):
        for variant in self:
            variant_dto = VariantDTO.from_odoo(variant)
            if not variant.mataa_id:
                variant.create_on_external()
            else:
                variant.update_on_external()

    def create_on_external(self):
        self.mataa_status = 'publish'

        variant_dto = VariantDTO.from_odoo(self)
        sync_result = VariantSyncService.create(self.product_tmpl_id.id, variant_dto, env=self.env)
        external_id = sync_result.get('data', {}).get('id')

        self.write({
            'mataa_id': external_id,
            'is_synced': True,
            'mataa_status': 'publish',
            'last_synced_quantity': self.get_mataa_quantity(),
            'sync_status': 'synced',
        })

        return self

    def update_on_external(self):
        variant_dto = VariantDTO.from_odoo(self)
        sync_result = VariantSyncService.update(variant_dto['id'], variant_dto, env=self.env)

        self.with_context(pre_sync=True).write({'last_synced_quantity': self.get_mataa_quantity()})

        if sync_result and self.sync_status != 'synced':
            self.with_context(init_sync_status=True).sync_status = 'synced'

        return self

    def batch_update_on_external(self, grouped_by):
        # TODO : after the new product catalog the batch update needs fixing
        variants_dto = []
        json_batch = {}
        for record in self:
            variant_dto = VariantDTO.from_odoo(record)
            variants_dto.append(variant_dto)
        json_batch = VariantSyncService.update_json(json_batch, variants_dto)
        sync_result = VariantSyncService.batch_update(json_batch, grouped_by.mataa_id, env=self.env)
        if sync_result:
            self.with_context(init_sync_status=True).write({
                'sync_status': 'synced',
            })
            self.env.cr.commit()
        return self

    def mark_for_sync(self):
        self.write({'sync_status': 'to_be_synced'})

    def toggle_mataa_status(self):
        for record in self:
            if record.mataa_status == 'publish':
                record.mataa_status = 'draft'
            else:
                record.mataa_status = 'publish'

    @api.model
    def get_grouped_records(self, records):
        records = records.sorted(lambda r: r.write_date, reverse=True)
        grouped_products = defaultdict(list)
        for product in records:
            grouped_products[product.product_tmpl_id].append(product)
        return dict(list(grouped_products.items())[:40])  # since that product.product depend on product.template
