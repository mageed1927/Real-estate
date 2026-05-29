from odoo import models, fields, api


class ImportInherit(models.TransientModel):
    _inherit = 'base_import.import'

    def execute_import(self, fields, columns, options, dryrun=False):
        if 'test_import' not in self._context:
            import_result = super(ImportInherit, self).with_context(test_import=dryrun).execute_import(fields, columns, options, dryrun)
        else:
            import_result = super(ImportInherit, self).execute_import(fields, columns, options, dryrun)

        return import_result