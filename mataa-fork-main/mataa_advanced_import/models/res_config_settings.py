# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    quick_sync_url = fields.Char(string="Quick Sync Url", config_parameter="mataa_advanced_import.quick_sync_url")
    import_pick_type_id = fields.Many2one('stock.picking.type', string="Default receipt operation",
                                           help="Default receipt operation for imported PO",
                                           config_parameter="mataa_advanced_import.import_pick_type_id")

    ems_import_issues_daily = fields.Char(
        string="EMS Import Issues Daily Link",
        config_parameter="mataa_advanced_import.ems_import_issues_daily"
    )
    ems_import_issues_monthly = fields.Char(
        string="EMS Import Issues Monthly Link",
        config_parameter="mataa_advanced_import.ems_import_issues_monthly"
    )
