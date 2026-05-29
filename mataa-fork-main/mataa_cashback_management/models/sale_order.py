# -*- coding: utf-8 -*-
from odoo import fields, models, api, _
import logging

_logger = logging.getLogger(__name__)

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    cashback_processed = fields.Boolean(
        string="Cashback Processed",
        default=False,
        copy=False,
        help="Technical field to prevent creating duplicate cashback payments."
    )

    cashback_payment_ids = fields.Many2many(
        'account.payment',
        string="Cashback Payments",
        copy=False
    )

    applied_cashback_program_id = fields.Many2one(
        'cashback.program',
        string="Applied Cashback Program",
        copy=False
    )

    cashback_approval_required = fields.Boolean(
        compute='_compute_cashback_approval_required'
    )

    def _compute_cashback_approval_required(self):
        for order in self:

            is_correct_state = (
                    order.mata_shipment_state == 'partially_delivered' and not order.cashback_processed
            )


            qualifies_for_cashback = order._get_first_applicable_cashback_program() is not None


            order.cashback_approval_required = is_correct_state and qualifies_for_cashback

    def action_approve_cashback(self):
        self.ensure_one()
        program = self._get_first_applicable_cashback_program()
        if program:
            self._process_cashback_for_program(program)
            activity = self.env['mail.activity'].search([
                ('res_id', '=', self.id),
                ('res_model', '=', 'sale.order'),
                ('summary', 'ilike', 'مراجعة ومنح كاش باك')
            ], limit=1)
            if activity:
                activity.action_feedback(feedback='Approved and processed.')

    def _create_cashback_approval_notifications(self, program):
        self.ensure_one()

        if program.activity_user_id:
            self.activity_schedule(
                'mail.activity_data_todo',
                summary=_('مراجعة ومنح كاش باك للطلبية %s') % self.name,
                user_id=program.activity_user_id.id,
            )

        if program.helpdesk_team_id:
            self.env['helpdesk.ticket'].create({
                'name': _('مطلوب موافقة على كاش باك للطلبية %s') % self.name,
                'partner_id': self.partner_id.id,
                'team_id': program.helpdesk_team_id.id,
                'description': _(
                    'الرجاء مراجعة الطلبية %s التي تم توصيلها جزئيًا والموافقة على منح الكاش باك المستحق.') % self.name,
            })

    def action_view_cashback_payments(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Cashback Payments'),
            'res_model': 'account.payment',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', self.cashback_payment_ids.ids)],
        }

    def write(self, vals):
        res = super(SaleOrder, self).write(vals)

        if 'mata_shipment_state' in vals:
            for order in self:
                if order.is_refund_order or order.cashback_processed:
                    continue

                program = order._get_first_applicable_cashback_program()
                if not program:
                    continue

                if vals['mata_shipment_state'] == 'fully_delivered':
                    order._process_cashback_for_program(program)
                elif vals['mata_shipment_state'] == 'partially_delivered':
                    order._create_cashback_approval_notifications(program)


        return res

    def _get_first_applicable_cashback_program(self):
        """Finds the first active cashback program that this order qualifies for."""
        self.ensure_one()

        order_date = self.date_order.date()

        programs = self.env['cashback.program'].search([
            ('active', '=', True),
            ('start_date', '<=', order_date),
            ('end_date', '>=', order_date),
        ])

        for program in programs:
            for rule in program.rule_ids:
                if self._order_matches_rule(rule):
                    return program

        return None

    def _order_matches_rule(self, rule):
        """Checks if the entire order matches a specific rule's conditions."""
        self.ensure_one()

        program = rule.program_id

        limit = program.usage_limit_per_customer
        if limit > 0:
            previous_usages = self.env['sale.order'].search_count([
                ('partner_id', '=', self.partner_id.id),
                ('applied_cashback_program_id', '=', program.id),
                ('id', '!=', self.id)
            ])
            if previous_usages >= limit:
                _logger.info(
                    f"Cashback for order {self.name} skipped: Customer has reached the usage limit for program {program.name}.")
                return False

        if rule.partner_ids and self.partner_id not in rule.partner_ids:
            return False

        eligible_lines_value = 0
        for line in self.order_line.filtered(lambda l: not l.is_delivery and l.mataa_qty_delivered > 0):
            if self._line_matches_rule(line, rule):
                eligible_lines_value += line.price_unit * line.mataa_qty_delivered

        if eligible_lines_value < rule.minimum_amount:
            return False

        return True

    def _line_matches_rule(self, line, rule):
        """Checks if a single order line matches a rule's product-related conditions."""
        # Product condition
        if rule.product_ids and line.product_id not in rule.product_ids:
            return False

        # Internal Category condition
        if rule.category_id and line.product_id.categ_id != rule.category_id:
            return False

        # Brand condition
        if rule.brand_ids and line.product_id.product_brand_id not in rule.brand_ids:
            return False

        # Website Category condition
        if rule.public_categ_ids and not any(categ in line.product_id.public_categ_ids for categ in rule.public_categ_ids):
            return False

        # Vendor condition
        if rule.vendor_ids:
            product_vendors = line.product_id.seller_ids.mapped('partner_id')
            if not any(vendor in product_vendors for vendor in rule.vendor_ids):
                return False

        return True

    def _process_cashback_for_program(self, program):
        """Calculates and creates the cashback payment for a given program."""
        self.ensure_one()

        total_eligible_value = 0

        for rule in program.rule_ids:
            if self._order_matches_rule(rule):
                rule_eligible_value = 0
                for line in self.order_line.filtered(lambda l: not l.is_delivery and l.mataa_qty_delivered > 0):
                    if self._line_matches_rule(line, rule):
                        rule_eligible_value += line.price_unit * line.mataa_qty_delivered

                if rule_eligible_value >= rule.minimum_amount:
                    total_eligible_value = rule_eligible_value
                    break

        if total_eligible_value > 0:
            cashback_amount = round(total_eligible_value * program.cashback_percentage, 2)

            if cashback_amount > 0:

                if program.creation_method == 'payment':

                    if not program.journal_id:
                        _logger.error(
                            f"Cashback for order {self.name} skipped: Payment Journal is not set in the program.")
                        return

                    payment_vals = {
                        'partner_id': self.partner_id.id,
                        'amount': cashback_amount,
                        'journal_id': program.journal_id.id,
                        'payment_type': 'inbound',
                        'partner_type': 'customer',
                        'ref': f'كاش باك للطلب رقم {self.mata_order_id}',
                    }
                    payment = self.env['account.payment'].create(payment_vals)
                    payment.action_post()
                    self.cashback_payment_ids = [(4, payment.id)]
                    body = _('Cashback payment %s of %s %s successfully created.') % (payment.name, cashback_amount,
                                                                                      self.currency_id.symbol)
                    log_message = f"Created cashback payment {payment.name} for order {self.name}"

                else:  # program.creation_method == 'journal_entry'

                    if not program.entry_journal_id or not program.expense_account_id:
                        _logger.error(
                            f"Cashback for order {self.name} skipped: Journal for Entry or Expense Account are not set in the program.")
                        return

                    move_lines = [

                        (0, 0, {
                            'account_id': program.expense_account_id.id,
                            'name': f'كاش باك للطلب رقم {self.mata_order_id}',
                            'debit': cashback_amount,
                            'credit': 0.0,
                        }),

                        (0, 0, {
                            'account_id': self.partner_id.property_account_receivable_id.id,
                            'partner_id': self.partner_id.id,
                            'name': f'كاش باك للطلب رقم {self.mata_order_id}',
                            'debit': 0.0,
                            'credit': cashback_amount,
                        }),
                    ]
                    move = self.env['account.move'].create({
                        'ref': f'كاش باك للطلب رقم {self.mata_order_id}',
                        'journal_id': program.entry_journal_id.id,
                        'line_ids': move_lines,
                    })
                    move.action_post()
                    body = _('Cashback journal entry %s of %s %s successfully created.') % (move.name, cashback_amount,
                                                                                            self.currency_id.symbol)
                    log_message = f"Created cashback journal entry {move.name} for order {self.name}"

                self.applied_cashback_program_id = program.id


                if program.tag_to_apply_id:
                    self.write({'mataa_tag_ids': [(4, program.tag_to_apply_id.id)]})


                self.cashback_processed = True

                if body:
                    self.message_post(body=body)
                if log_message:
                    _logger.info(log_message)