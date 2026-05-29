from odoo import models, fields, api

class SuspendCustomerWizard(models.TransientModel):
    _name = 'suspend.customer.wizard'
    _description = 'Suspend Customer Wizard'

    partner_id = fields.Many2one('res.partner', string="Customer")
    reason = fields.Text(string="Reason", required=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_model = self._context.get('active_model')
        active_id = self._context.get('active_id')
        if active_model == 'res.partner' and active_id:
            res['partner_id'] = active_id
        return res

    def action_confirm(self):
        self.ensure_one()
        for rec in self:
            rec.partner_id.toggle_suspension(reason=rec.reason)

        return {'type': 'ir.actions.act_window_close'}