# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from ..services.city_service import CityService


class MataaCity(models.Model):
    _name = "mataa.city"
    _inherit = ['mail.thread']
    _description = 'Mataa City'

    name = fields.Char(string="City")
    code = fields.Char(string="Code")

    parent_id = fields.Many2one('mataa.city', string="Parent City")

    def write(self, vals):
        res = super().write(vals)

        cost_fields_changed = any(field in vals for field in ['camex_total_cost', 'line_total_cost', 'name', 'code'])

        if cost_fields_changed:
            for rec in self:
                try:
                    CityService.send_area_update(self.env, rec, vals)
                except Exception as e:
                    raise UserError(_("Failed to update area in EMS: %s" % e))

        return res