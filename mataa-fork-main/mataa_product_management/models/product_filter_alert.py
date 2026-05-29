from odoo import models, fields, api
from odoo.tools.safe_eval import safe_eval

class ProductFilterAlert(models.Model):
    _name = 'product.filter.alert'
    _description = 'Product Filter Alert'

    name = fields.Char(string="Filter Name", required=True)
    domain = fields.Char(string="Filter", required=True, default="[]")
    product_count = fields.Integer(string="Current Matches", default=0, store=True)
    enabled = fields.Boolean(string="Enabled", default=True)

    def _cron_update_product_alerts_count(self):
        for alert in self.search([]):
            if alert.enabled:
                alert.product_count = self.env['product.product'].search_count(safe_eval(alert.domain))

    @api.model_create_multi
    def create(self, vals_list):
        res = super(ProductFilterAlert, self).create(vals_list)
        res._cron_update_product_alerts_count()
        return res

    def action_open_product_list(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.name,
            'res_model': 'product.product',
            'view_mode': 'tree,form',
            'views': [(False, 'tree'), (False, 'form')],
            'domain': safe_eval(self.domain or '[]'),
            'target': 'current',
        }