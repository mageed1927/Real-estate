# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class SaleOrderCompensationWizard(models.TransientModel):
    _name = 'sale.order.compensation.wizard'
    _description = 'Sale Order Compensation Wizard'

    sale_order_id = fields.Many2one(
        'sale.order',
        string='Sale Order',
        required=True,
        readonly=True
    )
    
    compensation_reason_id = fields.Many2one(
        'compensation.reason',
        string='Compensation Reason',
        required=True,
    )
    
    compensation_description = fields.Text(
        string='Compensation Description',
        required=True,
    )
    
    compensation_amount = fields.Monetary(
        string='Compensation Amount',
        currency_field='currency_id',
        required=True,
    )
    
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        related='sale_order_id.currency_id',
        readonly=True
    )
    
    max_compensation_amount = fields.Monetary(
        string='Maximum Compensation Amount',
        currency_field='currency_id',
        readonly=True,
    )
    
    order_total = fields.Monetary(
        string='Order Total',
        currency_field='currency_id',
        related='sale_order_id.amount_total',
        readonly=True
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if self.env.context.get('default_sale_order_id'):
            sale_order = self.env['sale.order'].browse(
                self.env.context.get('default_sale_order_id')
            )
            res['max_compensation_amount'] = sale_order._get_max_compensation_amount()
        return res

    @api.constrains('compensation_amount')
    def _check_compensation_amount(self):
        for wizard in self:
            if wizard.compensation_amount <= 0:
                raise ValidationError(_('Compensation amount must be greater than zero.'))
            
            if wizard.compensation_amount > wizard.max_compensation_amount:
                raise ValidationError(
                    _('Compensation amount cannot exceed the maximum allowed amount of %s.')
                    % wizard.max_compensation_amount
                )

    def action_confirm_compensation(self):
        self.ensure_one()
        
        self._check_compensation_amount()
        
        self.sale_order_id.write({
            'compensation_reason_id': self.compensation_reason_id.id,
            'compensation_description': self.compensation_description,
            'compensation_amount': self.compensation_amount,
            'compensation_user_id': self.env.user.id,
            'compensation_date': fields.Datetime.now(),
        })
        
        self._create_compensation_journal_entry()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Compensation Applied'),
                'message': _('Compensation of %s has been applied to order %s.') % (
                    self.compensation_amount, self.sale_order_id.name
                ),
                'type': 'success',
                'next': {
                    'type': 'ir.actions.client',
                    'tag': 'soft_reload',
                },
            }
        }

    def _create_compensation_journal_entry(self):
        compensation_journal_id = self.env['ir.config_parameter'].sudo().get_param(
            'mataa_order_management.compensation_journal_id'
        )
        compensation_account_id = self.env['ir.config_parameter'].sudo().get_param(
            'mataa_order_management.compensation_account_id'
        )
        
        if not compensation_journal_id or not compensation_account_id:
            raise UserError(_('Compensation journal and account must be configured in settings.'))
        
        partner_receivable_account = self.sale_order_id.partner_id.property_account_receivable_id
        if not partner_receivable_account:
            raise UserError(_('Partner %s does not have a receivable account configured.') % 
                          self.sale_order_id.partner_id.name)
        
        reference = _('Compensation on order %s due to %s.') % (
            self.sale_order_id.name,
            self.compensation_reason_id.description
        )
        
        move_lines = [
            {
                'account_id': int(compensation_account_id),
                'name': reference,
                'debit': self.compensation_amount,
                'credit': 0.0,
                'partner_id': self.sale_order_id.partner_id.id,
            },
            {
                'account_id': partner_receivable_account.id,
                'name': reference,
                'debit': 0.0,
                'credit': self.compensation_amount,
                'partner_id': self.sale_order_id.partner_id.id,
            }
        ]
        
        move_vals = {
            'journal_id': int(compensation_journal_id),
            'date': fields.Date.today(),
            'ref': reference,
            'line_ids': [(0, 0, line) for line in move_lines],
        }
        
        move = self.env['account.move'].sudo().create(move_vals)
        move.action_post()
        if move:
            self.sale_order_id.write({
                'compensation_journal_entry_id': move.id,
            })
        return move
