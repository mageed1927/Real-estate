# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    camex_secret_key = fields.Char(string='Camex Secret Key',
                                   config_parameter='delivery_camex.camex_secret_key',default=False)

    camex_responsible_user_id = fields.Many2one(
        'res.users',
        string='Responsible for Partial Returns',
        config_parameter='delivery_camex.camex_responsible_user_id',
        help="The user who will be assigned activities for Camex partial returns."
    )