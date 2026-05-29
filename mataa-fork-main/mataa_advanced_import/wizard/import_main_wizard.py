from odoo import models, api
from odoo.exceptions import UserError
from odoo.tools.translate import _



class ImportMainWizard(models.TransientModel):
    _name = 'import.main.wizard'
    _description = 'Import Main Wizard'

    @api.model
    def action_open_import_variants(self, *args):
        return {
            'name': 'Import Variants',
            'type': 'ir.actions.act_window',
            'res_model': 'import.variants.wizard',
            'view_mode': 'form',
            'target': 'new',
        }

    @api.model
    def action_open_import_quick(self, *args):
        return {
            'name': 'Import Quick',
            'type': 'ir.actions.act_window',
            'res_model': 'import.quick.wizard',
            'view_mode': 'form',
            'target': 'new',
        }

    @api.model
    def action_open_import_po(self, *args):
        return {
            'name': 'Import POs',
            'type': 'ir.actions.act_window',
            'res_model': 'import.po.wizard',
            'view_mode': 'form',
            'target': 'new',
        }

    def action_download_ems_daily(self):
        url = self.env['ir.config_parameter'].sudo().get_param('mataa_advanced_import.ems_import_issues_daily')
        if not url:
            raise UserError(_("Daily Sync URL is not configured in Settings."))
        return {
            'type': 'ir.actions.act_url',
            'url': url,
            'target': 'new',
        }

    def action_download_ems_monthly(self):
        url = self.env['ir.config_parameter'].sudo().get_param('mataa_advanced_import.ems_import_issues_monthly')
        if not url:
            raise UserError(_("Monthly Sync URL is not configured in Settings."))
        return {
            'type': 'ir.actions.act_url',
            'url': url,
            'target': 'new',
        }
