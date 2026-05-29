from odoo import models, api
from odoo.exceptions import ValidationError

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('partner_id'):
                partner = self.env['res.partner'].browse(vals['partner_id'])
                if partner.is_suspended:
                    raise ValidationError(("This customer is suspended. Please contact the administrator."))
        return super().create(vals_list)