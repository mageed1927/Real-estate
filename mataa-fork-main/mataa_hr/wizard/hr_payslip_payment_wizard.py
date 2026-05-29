from odoo import models, fields, api, _
from odoo.exceptions import UserError


class HrPayslipPaymentWizard(models.TransientModel):
    _name = 'hr.payslip.payment.wizard'
    _description = 'Batch Payslip Payment'

    journal_id = fields.Many2one(
        'account.journal',
        string='Payment Journal',
        required=True,
        domain="[('type', 'in', ('bank', 'cash'))]"
    )
    payment_date = fields.Date(string='Payment Date', required=True, default=fields.Date.context_today)
    payslip_ids = fields.Many2many('hr.payslip', string='Payslips')

    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)

    employee_count = fields.Integer(
        string="Number of Employees",
        compute="_compute_totals"
    )


    total_amount = fields.Monetary(
        string="Total Amount",
        compute="_compute_totals",
        currency_field='currency_id'
    )

    warning_message = fields.Char(string="Warning Message", readonly=True)

    @api.depends('payslip_ids')
    def _compute_totals(self):
        for wizard in self:
            wizard.employee_count = len(wizard.payslip_ids)
            wizard.total_amount = sum(wizard.payslip_ids.mapped('net_wage'))

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_ids = self.env.context.get('active_ids')
        if active_ids:
            selected_payslips = self.env['hr.payslip'].browse(active_ids)
            valid_payslips = selected_payslips.filtered(lambda p: p.state == 'done')

            invalid_count = len(selected_payslips) - len(valid_payslips)

            if invalid_count > 0:
                res['warning_message'] = f"تنبيه: تم استبعاد عدد ({invalid_count}) مرتب لأن حالتها ليست (معتمد - Done)."

            res['payslip_ids'] = [(6, 0, valid_payslips.ids)]

        return res

    def action_create_batch_payment(self):
        valid_payslips = self.payslip_ids.filtered(lambda p: p.state == 'done')
        if not valid_payslips:
            raise UserError("الرجاء تحديد مرتبات معتمدة (Done) فقط.")

        move_lines = []
        total_amount = 0.0


        for slip in valid_payslips:
            amount = slip.net_wage
            partner = slip.employee_id.work_contact_id

            if not partner:
                raise UserError(f"الموظف {slip.employee_id.name} لا يملك شريك مالي مرتبط.")

            account_id = partner.property_account_payable_id.id

            if slip.move_id and slip.move_id.state == 'posted':
                slip_credit_line = slip.move_id.line_ids.filtered(
                    lambda l: l.partner_id.id == partner.id and l.credit > 0
                )
                if slip_credit_line:
                    account_id = slip_credit_line[0].account_id.id

            move_lines.append((0, 0, {
                'name': f"سداد مرتب {slip.employee_id.name} - {slip.date_from.strftime('%m/%Y')}",
                'account_id': account_id,
                'partner_id': partner.id,
                'debit': amount,
                'credit': 0.0,
            }))
            total_amount += amount


        move_lines.append((0, 0, {
            'name': f"سداد مرتبات مجمعة - {len(valid_payslips)} موظفين",
            'account_id': self.journal_id.default_account_id.id,
            'debit': 0.0,
            'credit': total_amount,
        }))

        move_vals = {
            'journal_id': self.journal_id.id,
            'date': self.payment_date,
            'ref': f"دفعة مرتبات مجمعة",
            'line_ids': move_lines,
        }
        move = self.env['account.move'].create(move_vals)
        move.action_post()

        for slip in valid_payslips:
            if hasattr(slip, 'action_payslip_paid'):
                slip.action_payslip_paid()
            else:
                slip.write({'state': 'paid'})

            partner = slip.employee_id.work_contact_id
            if partner and slip.move_id and slip.move_id.state == 'posted':
                credit_lines = slip.move_id.line_ids.filtered(
                    lambda l: l.partner_id.id == partner.id and l.credit > 0 and not l.reconciled
                )
                debit_lines = move.line_ids.filtered(
                    lambda l: l.partner_id.id == partner.id and l.debit > 0 and not l.reconciled
                )

                if credit_lines and debit_lines:
                    if credit_lines[0].account_id.id == debit_lines[0].account_id.id:
                        if credit_lines[0].account_id.reconcile:
                            (credit_lines[0] + debit_lines[0]).reconcile()

        return {
            'name': 'Grouped Salary Payment',
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': move.id,
        }