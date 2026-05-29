from odoo import models, fields, api
import json
import logging
_logger = logging.getLogger(__name__)

from odoo.exceptions import UserError
from ..services.product_sync_service import ProductSyncService
from ..services.variant_sync_service import VariantSyncService
from ..data_models.product_dto import ProductDTO


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    mataa_id = fields.Char(string="Mataa ID")

    # TODO : this needs fixing and mapping after new product-catalog system integration
    mataa_status = fields.Selection([
        ('unspecified', 'Unspecified'),
        ('draft', 'draft'),
        ('publish', 'Published'),
    ], string='Status', default='unspecified')

    is_synced = fields.Boolean(string="Is Synced", default=False, tracking=True)
    product_temp_synced_date = fields.Datetime(string="Synced Date", store=True, readonly=True)
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


    @api.model
    def create(self, vals):
        if self.env.context.get('test_import'):
            return super(ProductTemplate, self).create(vals)

        if self.env.context.get('pre_sync'):
            return super(ProductTemplate, self).create(vals)

        created = super(ProductTemplate, self).create(vals)

        return created

    def write(self, vals):
        disable_async_sync = bool(self.env['ir.config_parameter']
                                  .sudo().get_param('mataa_external_sync.asynchronous_sync'))

        if 'is_synced' in vals and vals['is_synced']:
            now = fields.Datetime.now()
            for rec in self:
                rec.product_temp_synced_date = now

        if self.env.context.get('test_import'):
            return super(ProductTemplate, self).write(vals)

        if self.env.context.get('pre_sync'):
            return super(ProductTemplate, self).write(vals)

        updated = super(ProductTemplate, self).write(vals)
        # if set(vals.keys()).issubset({'product_seo_keywords'}):
        #     return updated
        #
        #
        # if self.env.context.get('skip_external_sync'):
        #     return updated
        # trigger_fields = {
        #     'name', 'list_price', 'barcode', 'default_code',
        #     'active', 'attribute_line_ids',}
        #
        # if not trigger_fields.intersection(vals.keys()):
        #     return updated


        for record in self:
            if record.mataa_id:
                if disable_async_sync:
                    # Will be synced by cron job
                    if not self.env.context.get('init_sync_status', False) and record.sync_status != 'to_be_synced':
                        record.mark_for_sync()

                    new_variants = record.product_variant_ids.filtered(lambda v: not v.mataa_id)
                    old_variants = (record.product_variant_ids - new_variants)

                    if not self.env.context.get('init_sync_status', False):
                        new_variants.sync_variants()
                        old_variants.mark_for_sync()
                else:
                    record.update_on_external()
                    record.product_variant_ids.sync_variants()
        return updated

    def unlink(self):
        for record in self:
            # Use savepoint to isolate each deletion attempt
            try:
                with self.env.cr.savepoint():
                    if record.is_synced and record.mataa_id:
                        ProductSyncService.delete(record.id, env=self.env)

                    super(ProductTemplate, record).unlink()

            except Exception as e:
                _logger.warning(
                    f"Could not delete product template {record.id}: {e}"
                )
                continue

        return True

    def sync_templates(self):
        for template in self:
            template.mataa_status = 'publish'

            if not template.mataa_id:
                template.create_on_external()
            else:
                template.update_on_external()

            template.product_variant_ids.sync_variants()

    def sync_selected(self):
        self.sync_templates()

    def create_on_external(self):
        # Restriction check before syncing
        is_restricted = self.check_product_restriction()
        if is_restricted:
            raise UserError(f"Product '{self.default_code}' has restricted tags. Sync prevented.")
        product_dto = ProductDTO.from_odoo(self)
        sync_result = ProductSyncService.create(product_dto, env=self.env)

        external_id = sync_result.get('data', {}).get('id')

        self.write({
            'mataa_id': external_id,
            'is_synced': True,
            'sync_status': 'synced'
        })

        return self

    def update_on_external(self):
        product_dto = ProductDTO.from_odoo(self)
        if product_dto.get('images') == []:
            product_dto['images'].append(product_dto['mainImage'])
        sync_result = ProductSyncService.update(self.id, product_dto, env=self.env)

        if sync_result and self.sync_status != 'synced':
            self.with_context(init_sync_status=True).sync_status = 'synced'

        return self

    def batch_update_on_external(self, grouped_by):
        # TODO : after the new product catalog the batch update needs fixing
        products_dto = []
        json_batch = {}
        for record in self:
            product_dto = ProductDTO.from_odoo(record)
            products_dto.append(product_dto)
        json_batch = ProductSyncService.update_json(json_batch, products_dto)
        sync_result = ProductSyncService.batch_update(json_batch, env=self.env)
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
        return {'no_groupment': records}

    def get_restricted_tags(self):
        return self.env.company.restricted_product_tag_ids

    def check_product_restriction(self, restricted_tags=None):
        if restricted_tags is None:
            restricted_tags = self.get_restricted_tags()
        restricted = self.product_tag_ids & restricted_tags
        return bool(restricted)


    def create_on_external_v2(self):
        for template in self:
            template_data = {
                "title": template.name,
                "description": template.description_sale,
                "sku": template.default_code,
                "brandName": template.product_brand_id.name,
                "warehouseForginKey": None,
                "salesPrice": template.list_price,
                "regularPrice": template.regular_price,
                "state": 1 if template.mataa_status == 'publish' else (2 if template.mataa_status == 'draft' else 0),
                "mainImage": template.main_image,
                "weight": template.weight,
                "tags": [tag.id for tag in template.product_tag_ids],
                "attributes": [attr_line.attribute_id.id for attr_line in template.attribute_line_ids] if template.attribute_line_ids else [],
                "images": [image.url for image in template.image_url_ids ],
                "categories": [categ_id for categ_id in template.public_categ_ids.ids],
                "categoryString": template.categ_id.name,
                "mattaId": template.mataa_id if template.mataa_id else None,
                "odooId": template.id,
                "keywords": [kw.name for kw in template.product_seo_keywords],
                "vendorOdooIds": [vendor.id for vendor in self.env['product.supplierinfo'].search([('product_tmpl_id', '=', template.id)])]
            }
            result_sync = ProductSyncService.create_with_details_v2(template_data, env=self.env)
            template_id = result_sync.get('data', {}).get('id')

            varients = self.env['product.product'].search([
                ('product_tmpl_id', '=', template.id)
            ])
            for variant in varients:
                variant_data = {
                    "productId": None,
                    "title": variant.name,
                    "description": variant.description_sale,
                    "sku": variant.default_code,
                    "barcode": variant.barcode,
                    "price": variant.regular_price,
                    "discountPrice": variant.lst_price,
                    "isOnStock": variant.get_mataa_quantity() > 0,
                    "isActive": variant.active,
                    "isOnDiscount": variant.regular_price != variant.lst_price,
                    "isPrimary": False,
                    "attributeOdooId": [attribute_value.product_attribute_value_id.id for attribute_value in variant.product_template_attribute_value_ids],
                    "warehouseForginKey": None,
                    "mattaId": variant.mataa_id if variant.mataa_id else None,
                    "odooId": variant.id
                }
                sync_result = VariantSyncService.create_with_details_v2(template.id, variant_data, env=self.env)
                external_id = sync_result.get('data', {}).get('id')
                variant.write({
                    'mataa_id': external_id if external_id else "",
                    'mataa_status': 'publish',
                    'is_synced': True,
                    'sync_status': 'synced'
                })
            template.write({
                'mataa_id': template_id if template_id else "",
                'mataa_status': 'publish',
                'is_synced': True,
                'sync_status': 'synced'
            })