from odoo import models, fields, api, _


class MataaCity(models.Model):
    _inherit = "mataa.city"

    line_zone_id = fields.Integer(tracking=True, copy=False)
    line_subzone_id = fields.Integer(tracking=True, copy=False)
    line_total_cost = fields.Float(string="Line Total Cost", tracking=True, default=1)

    def line_get_delivery_cost(self):
        self.ensure_one()
        return self.line_total_cost