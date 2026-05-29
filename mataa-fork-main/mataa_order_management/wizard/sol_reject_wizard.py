# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class SOLsRejectWizard(models.TransientModel):
    _name = 'sol.reject.wizard'
    _description = 'SOLs Reject Wizard'

    sale_order_id = fields.Many2one('sale.order', readonly=True, required=True)
    sale_order_line_ids = fields.Many2many('sale.order.line')

    def reject_selected_lines(self):
        team_id = self.sale_order_id.company_id.customer_support_team_id
        if not team_id:
            raise UserError(_("Miss configuration: No customer support team found"))

        line_details = ""
        i = 0
        for line in self.sale_order_line_ids:
            i += 1
            total_rejected = sum(line.rejection_ids.mapped('rejected_qty'))
            line_details += f"{i}. {line.product_id.name} - Rejected: {total_rejected} units<br/>"

        ticket_data = {
            'name': f'Order Lines Rejected: {self.sale_order_id.name}',
            'description': f"""Hello Customer Care Team, the following lines have been rejected:<br/>
            {line_details}
            """,
            'mataa_customer_id': self.sale_order_id.partner_id.id,
            'mataa_so_id': self.sale_order_id.id,
            'team_id': team_id.id,
            'company_id': self.sale_order_id.company_id.id,
        }
        self.env['helpdesk.ticket'].sudo().create(ticket_data)