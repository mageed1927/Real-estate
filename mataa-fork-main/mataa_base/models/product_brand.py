# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class ProductBrand(models.Model):
    _inherit = 'product.brand'

    vendor_ids = fields.Many2many(
        comodel_name='res.partner',
        relation='brand_vendor_rel',
        column1='brand_id',
        column2='partner_id',
        string='Vendors'
    )
    vendor_count = fields.Integer(compute="_compute_vendor_count")

    @api.depends('vendor_ids')
    def _compute_vendor_count(self):
        for rec in self:
            rec.vendor_count = len(rec.vendor_ids)

    def action_view_related_vendors(self):
        self.ensure_one()
        if len(self.vendor_ids) == 1:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Related Vendors'),
                'res_model': 'res.partner',
                'view_mode': 'form',
                'res_id': self.vendor_ids.id,
                'target': 'current',
            }
        elif len(self.vendor_ids) > 1:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Related Vendors'),
                'res_model': 'res.partner',
                'view_mode': 'tree,form',
                'domain': [('id', 'in', self.vendor_ids.ids)],
                'target': 'current',
            }
