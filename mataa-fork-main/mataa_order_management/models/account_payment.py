# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError

from ..services.wallet_service import WalletService


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    mataa_sale_order_id = fields.Many2one(
        'sale.order',
        string='Mataa Sale Order',
        readonly=True,
        help='Reference to the related Mataa Sale Order'
    )

    mataa_payment_id = fields.Many2one(
        'mataa.so.payment',
        string='Mataa Payment',
        readonly=True,
        help='Reference to the related Mataa Payment'
    )

    is_synced = fields.Boolean(string="Is Synced", default=False, readonly=True)

    sale_order_id = fields.Many2one('sale.order', string='Sale Order')

    def _prepare_move_line_default_vals(self, write_off_line_vals=None, **kwargs):
        res = super()._prepare_move_line_default_vals(write_off_line_vals=write_off_line_vals, **kwargs)

        for line_vals in res:
            if self.sale_order_id:
                line_vals['sale_order_id'] = self.sale_order_id.id

        return res

    def action_post(self):
        res = super(AccountPayment, self).action_post()
        if self._context.get('active_model', '') == "account.move.line":
            return res
        for payment in self:
            if (not payment.is_synced and payment.payment_type == "inbound"
                    and payment.partner_type == "customer"
                    and not payment.is_internal_transfer
                    and payment.partner_id.customer_rank > 0
                    and payment.partner_id.supplier_rank == 0
                    and not payment.partner_id.is_company):

                if not self.env.context.get('no_create'):
                    data = {
                        "isOnHold": False,
                        "amount": payment.amount,
                        "odooOwnerId": str(payment.partner_id.id),
                        "transactionSource": 1,
                        "transactionCode": str(payment.id),
                        "transactionOdooId": str(payment.id),
                        "statement": str(payment.ref or "") if payment else ""
                    }
                    WalletService.initiate_deposit(data)

                payment.is_synced = True

            if payment.journal_id.fee_percentage != 0 and payment.payment_type == "inbound":
                self._handle_payment_fee_calculation(payment)

        return res

    def _handle_payment_fee_calculation(self, payment):
        currency = payment.currency_id or payment.company_id.currency_id
        if not payment.journal_id.fee_account_id:
            raise UserError(_('Fee account is not configured for journal %s') % payment.journal_id.name)
        
        fee_amount = currency.round(payment.amount * (payment.journal_id.fee_percentage))
        
        if currency.is_zero(fee_amount):
            return
        
        move = payment.move_id
        if not move:
            return
        
        payment_accounts = payment.journal_id.inbound_payment_method_line_ids.mapped('payment_account_id')
        
        liquidity_line = next(
            (line for line in move.line_ids
             if payment_accounts and line.account_id.id in payment_accounts.ids and line.debit > 0.0),
            None
        )
        if not liquidity_line:
            return
        
        new_amount = currency.round(liquidity_line.debit - fee_amount)
        liquidity_update_vals = {
            'debit': new_amount,
        }
        fee_label = _('%s payment fees of %s%%', (liquidity_line.name or ''), 
                      payment.journal_id.fee_percentage * 100)
        fee_line_vals = {
            'move_id': move.id,
            'account_id': payment.journal_id.fee_account_id.id,
            'partner_id': payment.partner_id.id,
            'name': fee_label,
            'debit': fee_amount,
            'credit': 0.0,
        }
        move.with_context(skip_account_move_synchronization=True).write({
            'line_ids': [
                (1, liquidity_line.id, liquidity_update_vals),
                (0, 0, fee_line_vals),
            ]
        })




class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    sale_order_id = fields.Many2one('sale.order', string='Sale Order', store=True)