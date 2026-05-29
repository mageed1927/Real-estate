from odoo import models, fields


class AccountPayment(models.Model):
    _inherit = 'account.payment'


    payslip_id = fields.Many2one('hr.payslip', string="Related Payslip")

    def action_post(self):

        res = super(AccountPayment, self).action_post()


        for payment in self:
            if payment.payslip_id and payment.payslip_id.state == 'done':

                if hasattr(payment.payslip_id, 'action_payslip_paid'):
                    payment.payslip_id.action_payslip_paid()
                else:
                    payment.payslip_id.write({'state': 'paid'})

                payment._reconcile_payslip_payment()

        return res

    def _reconcile_payslip_payment(self):

        self.ensure_one()
        slip = self.payslip_id
        if not slip:
            return

        partner = slip.employee_id.work_contact_id

        if partner and slip.move_id and slip.move_id.state == 'posted' and self.move_id:

            credit_lines = slip.move_id.line_ids.filtered(
                lambda l: l.partner_id.id == partner.id and l.credit > 0 and not l.reconciled
            )

            debit_lines = self.move_id.line_ids.filtered(
                lambda l: l.partner_id.id == partner.id and l.debit > 0 and not l.reconciled
            )

            if credit_lines and debit_lines:
                if credit_lines[0].account_id.id == debit_lines[0].account_id.id:
                    if credit_lines[0].account_id.reconcile:
                        (credit_lines[0] + debit_lines[0]).reconcile()