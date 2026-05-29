# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ResPartner(models.Model):
    _inherit = 'res.partner'


    in_house_vendor = fields.Boolean("In House Vendor", default=False)
