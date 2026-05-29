# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    _inherit = 'res.partner'

    wallet_amount = fields.Float("Wallet Current Amount", compute='_compute_wallet_amount')

    is_suspended = fields.Boolean(string="Is Suspended", default=False)
    suspension_reason = fields.Text(string="Suspension Reason")

    def open_toggle_suspension_wizard(self):
        self.ensure_one()
        for partner in self:
            return {
                'name': _('Suspend customer'),
                'type': 'ir.actions.act_window',
                'res_model': 'suspend.customer.wizard',
                'view_mode': 'form',
                'target': 'new',
                'view_id': self.env.ref('mataa_customer_management.view_suspend_customer_wizard_form').id,
                'context': {
                    'active_model': self._name,
                    'active_id': partner.id,
                }
            }
    
    def toggle_suspension(self, reason=False):
        for partner in self:
            if not partner.is_suspended:
                partner.write({
                    'is_suspended': True,
                    'suspension_reason': reason
                })
            else:
                partner.is_suspended = False


    @api.depends('property_account_receivable_id')
    def _compute_wallet_amount(self):
        for partner_id in self:
            aml_ids = self.env['account.move.line'].search([
                ('parent_state', '=', 'posted'),
                ('partner_id', '=', partner_id.id),
                ('account_id', '=', partner_id.property_account_receivable_id.id)])
            partner_id.wallet_amount = sum(aml_ids.mapped('credit')) - sum(aml_ids.mapped('debit'))
            
    def _check_property_account_receivable(self):
        for partner_id in self:
            aml_ids = self.env['account.move.line'].search([
                ('partner_id', '=', partner_id.id),
                ('account_id', '=', partner_id.property_account_receivable_id.id)], limit=1)
            if aml_ids:
                raise ValidationError(_('The receivable account cannot be changed.'))
    def write(self, vals):
        if 'property_account_receivable_id' in vals:
            self._check_property_account_receivable()
        return super(ResPartner, self).write(vals)