from odoo import models, fields, api


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    zkteco_url = fields.Char(string="ZKTeco URL", config_parameter="zkteco.url")
    zkteco_username = fields.Char(string="ZKTeco Username", config_parameter="zkteco.username")
    zkteco_password = fields.Char(string="ZKTeco Password", config_parameter="zkteco.password")
