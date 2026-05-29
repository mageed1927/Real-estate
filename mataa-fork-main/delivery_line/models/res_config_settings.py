# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    line_secret_key = fields.Char(string='Line Secret Key',
                                   config_parameter='delivery_line.line_secret_key',default=False)

    line_default_sender_id = fields.Many2one(
        'res.partner',
        string="Default Sender Contact",
        config_parameter='delivery_line.default_sender_id',
        help="Default contact used for sender information in Line shipments"
    )