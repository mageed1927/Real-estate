# -*- coding: utf-8 -*-
import time

from odoo import api, models
import logging
import traceback

_logger = logging.getLogger(__name__)


class BaseModel(models.Model):
    _inherit = 'ir.model.fields'

    @api.model
    def run_sync(self, batch_size):
        """Run sync for edited records"""
        # batch_size = 10
        # TODO : this method needs fixing after the new product-catalog system

        field_ids = self.search([('name', '=', 'sync_status'), ('ttype', '=', 'selection')])
        try:
            for field in field_ids:
                records = self.env[field.model_id.model].search([('sync_status', '=', 'to_be_synced')])
                grouped_records = self.env[field.model_id.model].get_grouped_records(records)
                for grouped_by, grouped_elements in grouped_records.items():
                    for i in range(0, len(grouped_elements), batch_size):
                        batch_ids = records[i:i + batch_size]
                        batch_ids.batch_update_on_external(grouped_by)
        except Exception:
            self.env.cr.commit()
            _logger.warning('Mataa: Run sync stopped before ending: %s' % str(traceback.format_exc()))
            return
        return
