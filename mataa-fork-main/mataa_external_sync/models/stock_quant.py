from odoo import api, fields, models


class StockQuant(models.Model):
    _inherit = "stock.quant"

    @api.model
    def create(self, vals):

        disable_async_sync = bool(
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("mataa_external_sync.asynchronous_sync")
        )

        created = super(StockQuant, self).create(vals)

        # To Skip EMS Sync if the package has been unpacked only.
        if self.env.context.get("skip_mataa_quant_sync"):
            return created

        if created.product_id.mataa_id and self._should_sync(created):
            if disable_async_sync:
                created.product_id.mark_for_sync()
            else:
                created.product_id.update_on_external()

        return created

    def write(self, vals):
        disable_async_sync = bool(
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("mataa_external_sync.asynchronous_sync")
        )

        updated = super(StockQuant, self).write(vals)

        # To Skip EMS Sync if the package has been unpacked only.
        if self.env.context.get("skip_mataa_quant_sync"):
            return updated

        for record in self:
            if record.product_id.mataa_id and record._should_sync(record):
                if disable_async_sync:
                    record.product_id.mark_for_sync()
                else:
                    record.product_id.update_on_external()

        return updated

    def _should_sync(self, record):
        record.ensure_one()
        current_quantity = record.product_id.get_mataa_quantity()
        return current_quantity != record.product_id.last_synced_quantity

