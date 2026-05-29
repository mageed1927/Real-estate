from odoo import fields, models, api


class HrSalaryAttachment(models.Model):

    _inherit = 'hr.salary.attachment'

#TODO : implement this method in the next phase
    # @api.model
    # def create(self, vals_list):
    #     records = super().create(vals_list)
    #
    #     for record in records:
    #         input_type = record.deduction_type_id
    #         if not input_type:
    #             _logger.warning(f"No deduction_type_id set for Salary Attachment {record.id}. Skipping input creation.")
    #             continue
    #
    #         for employee in record.employee_ids:
    #             # Find payslips overlapping the start date of the attachment
    #             payslips = self.env['hr.payslip'].search([
    #                 ('employee_id', '=', employee.id),
    #                 ('state', 'in', ['draft', 'verify']),
    #                 ('date_from', '<=', record.date_start),
    #                 ('date_to', '>=', record.date_start),
    #             ])
    #
    #             for payslip in payslips:
    #                 self.env['hr.payslip.input'].create({
    #                     'payslip_id': payslip.id,
    #                     'input_type_id': input_type.id,
    #                     'name': record.description or 'Salary Attachment',
    #                     'code': input_type.code or f'ATTACHMENT_{record.id}',
    #                     'amount': record.monthly_amount,
    #                     'contract_id': payslip.contract_id.id,
    #                 })
    #
    #     return records
