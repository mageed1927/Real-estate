# -*- coding: utf-8 -*-
import logging

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from markupsafe import Markup
from ..services.sale_order_service import SaleOrderSyncService
from odoo.tools import float_compare

_logger = logging.getLogger(__name__)


class SwitchPaymentMethodWizard(models.TransientModel):
    _name = 'switch.payment.method.wizard'
    _description = 'Switch Payment Method Wizard'

    sale_order_id = fields.Many2one(
        'sale.order',
        string='Sale Order',
        required=True,
        readonly=True,
        default=lambda self: self.env.context.get('active_id')
    )

    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        related='sale_order_id.currency_id',
        readonly=True
    )

    use_existing_payment = fields.Boolean(
        string='Use Existing Payment Method',
        help='Use existing wallet payment instead of creating a new one'
    )

    existing_payment_id = fields.Many2one(
        'mataa.so.payment',
        string='Existing Wallet Payment',
        domain="[('sale_order_id', '=', sale_order_id), ('code', '=', wallet_journal_code)]"
    )

    amount = fields.Monetary(
        string='Amount to Convert',
        required=True,
        help='Amount to move between payment methods'
    )

    wallet_journal_code = fields.Char(
        string='Wallet Journal Code',
        compute='_compute_wallet_journal_code',
        store=False
    )

    is_cod_to_wallet = fields.Boolean(
        default=lambda self: self.env.context.get('conversion_type') == 'cod_to_wallet',
        readonly=True,
    )

    @api.depends('sale_order_id')
    def _compute_wallet_journal_code(self):
        for wizard in self:
            if wizard.sale_order_id and wizard.sale_order_id.company_id.wallet_reservation_journal_id:
                wizard.wallet_journal_code = wizard.sale_order_id.company_id.wallet_reservation_journal_id.code
            else:
                wizard.wallet_journal_code = False

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        sale_order = self.env['sale.order'].browse(self.env.context.get('active_id'))
        if sale_order:
            if self.env.context.get('conversion_type') == 'wallet_to_cod':
                res['amount'] = sale_order.amount_total
        return res

    def action_confirm(self):
        self.ensure_one()

        order = self.sale_order_id
        if not order:
            raise UserError(_('No sale order found in context.'))

        if order.is_handled or order.mata_shipment_state:
            raise UserError(_('This order is already in closing/closed stage. Payment method updates are not allowed.'))

        if order.state not in ('draft', 'sent', 'sale'):
            raise UserError(_('Payment method updates are only allowed during order placement and before closing.'))

        wallet_journal = order.company_id.wallet_reservation_journal_id
        if not wallet_journal or not wallet_journal.code:
            raise UserError(_('Wallet reservation journal is not configured.'))

        if self.amount <= 0:
            raise UserError(_('Amount must be greater than zero.'))

        original_payments = self._get_payment_summary(order)

        if self.env.context.get('conversion_type') == 'cod_to_wallet':
            self._convert_cod_to_wallet(order, wallet_journal)
        else:
            if wallet_journal.code in order.mataa_payment_ids.mapped('code'):
                self._convert_wallet_to_cod(order, wallet_journal)
            else:
                raise UserError(_('Wallet payment does not exist for this order.'))

        total_payments_after_conversion = sum(order.mataa_payment_ids.mapped('amount'))
        
        if float_compare(total_payments_after_conversion, order.amount_total, precision_rounding=order.currency_id.rounding) > 0:
            raise UserError(_('Total payment amount cannot exceed order total.'))

        self._update_wallet_reservation_safely(order)

        self._log_payment_changes(order, original_payments)

        self._schedule_activity_to_update_delivery_partner(order)

        self._trigger_so_update_service(order)

        return {'type': 'ir.actions.act_window_close'}


    def _trigger_so_update_service(self, order):
        """
        Calculates payment distribution and calls the central sync service.
        """
        _logger.info(f"Preparing payload for EMS update for order {order.name}.")

        wallet_journal = order.company_id.wallet_reservation_journal_id
        e_journal_codes = [wallet_journal.code] + self.env['account.journal'].sudo().search(
            [('e_payment_journal', '=', True)]).mapped('code')

        cash_amount = 0.0
        wallet_amount = 0.0
        for payment in order.mataa_payment_ids:
            if payment.code in e_journal_codes:
                wallet_amount += payment.amount
            else:
                cash_amount += payment.amount

        payment_method_enum = 0
        if cash_amount > 0 and wallet_amount > 0:
            payment_method_enum = 6
        elif cash_amount > 0:
            payment_method_enum = 1
        elif wallet_amount > 0:
            payment_method_enum = 5

        payload = {
            "cashPayedAmount": cash_amount,
            "walletPayedAmount": wallet_amount,
            "paymentMethod": payment_method_enum,
        }

        try:
            _logger.info(f"Calling SaleOrderSyncService.update_payment_details for order {order.name} with payload: {payload}")
            SaleOrderSyncService.update_payment_details(order.mata_order_id, payload)
            _logger.info(f"Successfully triggered update service for order {order.name}")
        except Exception as e:
            _logger.error(f"An error occurred while trying to call the SO update service for order {order.name}: {e}")

    def _get_payment_summary(self, order):
        payment_summary = {}
        for payment in order.mataa_payment_ids:
            payment_summary[payment.code] = payment.amount
        return payment_summary

    def _convert_cod_to_wallet(self, order, wallet_journal):
        cod_payments = order.mataa_payment_ids.filtered(lambda p: p.code != wallet_journal.code and p.code not in self.env['account.journal'].sudo().search([('e_payment_journal', '=', True)]).mapped('code'))
        
        total_cod_available = sum(cod_payments.mapped('amount'))
        if self.amount > total_cod_available:
            raise UserError(_('Amount exceeds current COD amount: %s') % total_cod_available)

        if not self.use_existing_payment:
            customer_wallet_balance = order.partner_id.wallet_amount
            if customer_wallet_balance < self.amount:
                raise UserError(_('Insufficient wallet balance. Customer has %s %s, but %s %s is required.') % (
                    customer_wallet_balance, order.currency_id.symbol, self.amount, order.currency_id.symbol
                ))

        remaining_to_reduce = self.amount
        for cod_payment in cod_payments:
            if remaining_to_reduce <= 0:
                break
            reduce_amount = min(cod_payment.amount, remaining_to_reduce)
            cod_payment.amount -= reduce_amount
            remaining_to_reduce -= reduce_amount

        zero_cod_payments = cod_payments.filtered(lambda p: p.amount <= 0)
        if zero_cod_payments:
            zero_cod_payments.unlink()

        if self.use_existing_payment and self.existing_payment_id:
            target_payment = self.existing_payment_id
            target_payment.amount += self.amount
        else:
            existing = order.mataa_payment_ids.filtered(lambda p: p.code == wallet_journal.code)
            if existing:
                existing[0].amount += self.amount
            else:
                self.env['mataa.so.payment'].create({
                    'sale_order_id': order.id,
                    'code': wallet_journal.code,
                    'amount': self.amount,
                })

    def _convert_wallet_to_cod(self, order, wallet_journal):
        available_wallet_amount = order.get_total_e_payments()
        if self.amount > available_wallet_amount:
            raise UserError(_('Amount exceeds current wallet/e-payment amount: %s') % available_wallet_amount)

        cod_journal = None
        cod_payments = order.mataa_payment_ids.filtered(lambda p: p.code != wallet_journal.code)
        if cod_payments:
            cod_journal = self.env['account.journal'].sudo().search([('code', '=', cod_payments[0].code)], limit=1)
        elif order.carrier_id and order.carrier_id.cod_journal_id:
            cod_journal = order.carrier_id.cod_journal_id
        else:
            cod_journal = self.env['account.journal'].sudo().search([('type', '=', 'cash'), ('company_id', '=', order.company_id.id)], limit=1)

        if not cod_journal:
            raise UserError(_('No COD journal configured for this order.'))

        remaining_to_reduce = self.amount
        e_journal_codes = [wallet_journal.code] + self.env['account.journal'].sudo().search([('e_payment_journal', '=', True)]).mapped('code')
        
        ordered_payments = order.mataa_payment_ids.filtered(lambda p: p.code in e_journal_codes).sorted(key=lambda r: r.code != wallet_journal.code)
        
        for payment in ordered_payments:
            if remaining_to_reduce <= 0:
                break
            reduce_amount = min(payment.amount, remaining_to_reduce)
            payment.amount -= reduce_amount
            remaining_to_reduce -= reduce_amount

        zero_payments = order.mataa_payment_ids.filtered(lambda p: p.amount <= 0)
        if zero_payments:
            zero_payments.unlink()

        cod_payment = order.mataa_payment_ids.filtered(lambda p: p.code == cod_journal.code)
        if cod_payment:
            cod_payment[0].amount += self.amount
        else:
            self.env['mataa.so.payment'].create({
                'sale_order_id': order.id,
                'code': cod_journal.code,
                'amount': self.amount,
            })

    def _is_reservation_entry_valid(self, order):
        if not order.reservation_entry_id:
            return False
            
        if order.reservation_entry_id.state != 'posted':
            return False
            
        if order.reservation_entry_id.reversal_move_id:
            return False
            
        reservation_line = order.reservation_entry_id.line_ids.filtered(
            lambda l: l.account_id == order.company_id.wallet_reservation_account_id
        )
        
        return bool(reservation_line)

    def _safely_clear_wallet_reservation(self, order):
        if not order.reservation_entry_id:
            return
            
        try:
            order.clear_wallet_reservation()
        except UserError as e:
            if "already cleared" in str(e) or "not posted" in str(e):
                order.reservation_entry_id = False
            else:
                raise

    def _update_wallet_reservation_safely(self, order):

        current_e_payment_amount = order.get_e_payment_amount()
        
        if current_e_payment_amount <= 0:
            self._safely_clear_wallet_reservation(order)
            return
        
        if not order.reservation_entry_id:
            order.create_wallet_reservation()
            return
        
        if not self._is_reservation_entry_valid(order):
            order.reservation_entry_id = False
            order.create_wallet_reservation()
            return
        
        reservation_line = order.reservation_entry_id.line_ids.filtered(
            lambda l: l.account_id == order.company_id.wallet_reservation_account_id
        )
        
        current_reservation_amount = reservation_line[0].credit
        
        if abs(current_reservation_amount - current_e_payment_amount) < 0.01:
            return
        
        self._safely_clear_wallet_reservation(order)
        
        order.create_wallet_reservation()

    def _schedule_activity_to_update_delivery_partner(self, order):
        outgoing_pickings = order.picking_ids.filtered(
            lambda p: p.picking_type_code == 'outgoing' and p.state not in ('done', 'cancel')
        )
        if not outgoing_pickings:
            return
            
        for picking in outgoing_pickings:
                self._create_todo_activity(order, _('Update delivery partner with new order amount'))

    def _create_todo_activity(self, order, summary):
        activity_type = self.env.ref('mail.mail_activity_data_todo', raise_if_not_found=False)
        if activity_type:
            user_id = order.user_id.id or self.env.user.id
            self.env['mail.activity'].create({
                'res_id': order.id,
                'res_model_id': self.env['ir.model']._get_id(order._name),
                'activity_type_id': activity_type.id,
                'user_id': user_id,
                'date_deadline': fields.Date.today(self),
                'summary': summary,
            })

    def _log_payment_changes(self, order, original_payments):
        current_payments = self._get_payment_summary(order)
        
        conversion_type = self.env.context.get('conversion_type', 'unknown')
        amount = self.amount
        currency_symbol = order.currency_id.symbol or order.currency_id.name
        
        if conversion_type == 'cod_to_wallet':
            title = _('💳 Payment Switch: %s %s COD → Wallet') % (amount, currency_symbol)
        elif conversion_type == 'wallet_to_cod':
            title = _('💳 Payment Switch: %s %s Wallet → COD') % (amount, currency_symbol)
        else:
            title = _('💳 Payment Updated: %s %s') % (amount, currency_symbol)
        
        message_parts = [f'<strong>{title}</strong>']
        
        message_parts.append('<br><br><strong>📊 Before:</strong>')
        if original_payments:
            for code, amount in sorted(original_payments.items()):
                message_parts.append(f'<br>  {code}: {amount} {currency_symbol}')
        else:
            message_parts.append('<br>  None')
        
        message_parts.append('<br><strong>📊 After:</strong>')
        if current_payments:
            for code, amount in sorted(current_payments.items()):
                message_parts.append(f'<br>  {code}: {amount} {currency_symbol}')
        else:
            message_parts.append('<br>  None')
        
        message = Markup(''.join(message_parts))
        
        order.message_post(
            body=message,
            message_type='comment',
            subtype_xmlid='mail.mt_comment'
        )
