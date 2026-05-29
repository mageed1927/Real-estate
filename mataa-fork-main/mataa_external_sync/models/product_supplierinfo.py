from odoo import api, fields, models


class ProductSupplierinfo(models.Model):
    _inherit = 'product.supplierinfo'

    is_synced = fields.Boolean(related="product_id.is_synced", store=True)

    def write(self, vals):
        disable_async_sync = bool(self.env['ir.config_parameter']
                                  .sudo().get_param('mataa_external_sync.asynchronous_sync'))

        if self.env.context.get('pre_sync'):
            return super(ProductSupplierinfo, self).write(vals)

        updated = super(ProductSupplierinfo, self).write(vals)
        if 'min_qty' in vals:
            for record in self:
                if record.product_id and record.product_id.mataa_id:
                    if disable_async_sync:
                        # TODO: prevent to call that twice on creating/updating products
                        record.product_id.mark_for_sync()
                    else:
                        record.product_id.update_on_external()
                elif record.product_tmpl_id and record.product_tmpl_id.mataa_id:
                    if disable_async_sync:
                        # TODO: prevent to call that twice on creating/updating products
                        record.product_tmpl_id.mark_for_sync()
                    else:
                        record.product_tmpl_id.update_on_external()
        return updated
