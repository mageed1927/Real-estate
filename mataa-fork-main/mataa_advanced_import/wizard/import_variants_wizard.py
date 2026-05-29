# -*- coding: utf-8 -*-
import logging
from odoo import models, fields, _
from odoo.exceptions import UserError
from ..services.import_orchestrator_service import ImportOrchestratorService

_logger = logging.getLogger(__name__)


class ImportVariantsWizard(models.TransientModel):
    _name = 'import.variants.wizard'
    _description = 'Import Product Variants (Advanced)'

    import_file = fields.Binary(string="Upload File", required=True)
    file_name = fields.Char(string="File Name")

    behaviour = fields.Selection([
        ('create_update', 'Create / Update Variants'),
        ('only_update', 'Only Update Variants'),
    ], string='Import Behaviour', default='create_update', required=True)

    # ملف سجل واحد نهائي
    log_file_data = fields.Binary(string="Import Log", readonly=True, copy=False)
    log_file_name = fields.Char(string="Log File Name", readonly=True, copy=False)

    def import_variants(self):
        self.ensure_one()
        if not self.import_file or not self.file_name:
            raise UserError(_("Please upload a valid file."))

        service = ImportOrchestratorService(self.env)
        result = service.process_data(
            file_name=self.file_name,
            file_data=self.import_file,
            behaviour=self.behaviour,
        )

        self.write({
            "log_file_data": result.get("log_file_data"),
            "log_file_name": result.get("log_file_name"),
        })

        if result.get("has_errors"):
            # تنزيل تلقائي لملف السجل عند وجود أخطاء
            url = (
                f"/web/content/{self._name}/{self.id}/log_file_data"
                f"?download=true&filename={self.log_file_name or 'import_log.xlsx'}"
            )
            return {"type": "ir.actions.act_url", "url": url, "target": "self"}

        # إشعار نجاح أخضر عندما لا توجد أخطاء
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Import completed"),
                "message": _("All rows processed successfully."),
                "sticky": False,
                "type": "success",
            },
        }
