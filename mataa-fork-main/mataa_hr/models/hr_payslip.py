from odoo import models, fields, api


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    total_due_amount = fields.Monetary(
        string="Amount Due",
        compute='_compute_total_due',
    )

    apply_due_deduction = fields.Boolean(
        string="Deduct Amount",
        default=False
    )

    payment_ids = fields.One2many('account.payment', 'payslip_id', string='Payments')

    @api.depends('employee_id', 'employee_id.work_contact_id')
    def _compute_total_due(self):
        for slip in self:
            amount = 0.0
            partner = slip.employee_id.work_contact_id
            if partner:
                amount = partner.sudo().total_due

            slip.total_due_amount = amount if amount > 0 else 0.0

    def _prepare_line_values(self, line, account_id, date, debit, credit):
        res = super(HrPayslip, self)._prepare_line_values(line, account_id, date, debit, credit)

        if line.salary_rule_id.take_partner:
            partner = self.employee_id.work_contact_id
            if partner:
                res['partner_id'] = partner.id

        return res

    def _action_create_account_move(self):
        res = super(HrPayslip, self)._action_create_account_move()

        for slip in self:
            if slip.move_id and slip.move_id.state == 'draft':
                slip.move_id.action_post()

            partner = slip.employee_id.work_contact_id
            if slip.move_id and slip.move_id.state == 'posted' and partner:

                target_names = slip.line_ids.filtered(lambda l: l.salary_rule_id.take_partner).mapped('name')

                payslip_credit_lines = slip.move_id.line_ids.filtered(
                    lambda l: l.name in target_names and l.partner_id == partner and l.credit > 0
                )

                if payslip_credit_lines:
                    for p_line in payslip_credit_lines:
                        open_invoices = self.env['account.move.line'].search([
                            ('partner_id', '=', partner.id),
                            ('account_id', '=', p_line.account_id.id),
                            ('debit', '>', 0),
                            ('reconciled', '=', False),
                            ('move_id.state', '=', 'posted'),
                            ('id', '!=', p_line.id)
                        ])

                        if open_invoices:
                            (p_line + open_invoices).reconcile()

        return res

    def action_payslip_done(self):

        res = super(HrPayslip, self).action_payslip_done()


        for slip in self:
            if slip.contract_id:

                deductions_to_process = slip.contract_id.deduction_ids.filtered(
                    lambda l: l.date >= slip.date_from
                              and l.date <= slip.date_to
                              and not l.is_processed
                )


                if deductions_to_process:
                    deductions_to_process.sudo().write({'is_processed': True})

        return res

    def action_create_custom_payment(self):

        self.ensure_one()

        month_year = self.date_from.strftime('%m/%Y') if self.date_from else ''


        memo_text = f"مرتب {self.employee_id.name} لشهر {month_year}"


        return {
            'name': 'Salary Payment',
            'res_model': 'account.payment',
            'view_mode': 'form',
            'target': 'current',
            'type': 'ir.actions.act_window',
            'context': {
                'default_payment_type': 'outbound',
                'default_partner_type': 'supplier',
                'default_partner_id': self.employee_id.work_contact_id.id,
                'default_amount': self.net_wage,
                'default_ref': memo_text,
                'default_payslip_id': self.id,
            }
        }

    def action_view_payments(self):

        self.ensure_one()
        payments = self.payment_ids

        if len(payments) == 1:
            return {
                'name': 'Salary Payment',
                'type': 'ir.actions.act_window',
                'res_model': 'account.payment',
                'view_mode': 'form',
                'res_id': payments.id,
            }


        return {
            'name': 'Salary Payments',
            'type': 'ir.actions.act_window',
            'res_model': 'account.payment',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', payments.ids)],
        }