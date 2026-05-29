# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class MataaCity(models.Model):
    _inherit = "mataa.city"

    camex_city_id = fields.Char(string="Camex City ID", tracking=True)
    camex_city_name = fields.Char(string="Camex City Name", tracking=True)
    camex_area_name = fields.Char(string="Camex Area Name", tracking=True)
    camex_total_cost = fields.Float(string="Camex Total Cost", tracking=True)

    def camex_get_delivery_cost(self):
        self.ensure_one()
        return self.camex_total_cost