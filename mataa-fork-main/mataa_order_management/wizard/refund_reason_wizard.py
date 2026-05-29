from odoo import api, fields, models
from odoo.fields import Command
from odoo.exceptions import UserError

class SaleRefundWizard(models.TransientModel):
    _name = 'sale.order.refund.reason.wizard'
    _description = 'Wizard for Sale Order Refund Reason'

    refund_type = fields.Selection(
        [('replacement', 'استبدال'), ('refund', 'استرجاع')],
        string="نوع الطلب", required=True
    )
    
    # Removed refund_reason_ids from here, added line_ids
    line_ids = fields.One2many(
        'sale.order.refund.reason.wizard.line', 
        'wizard_id', 
        string="Refund Lines"
    )
    
    refund_description = fields.Text(string='الوصف', copy=False)

    refund_value_method = fields.Selection(
        [('wallet', 'محفظة'), ('cash', 'نقدا')],
        string=" القيمة ", required=True
    )

    @api.model
    def default_get(self, fields_list):
        res = super(SaleRefundWizard, self).default_get(fields_list)
        active_id = self.env.context.get('active_id')
        active_model = self.env.context.get('active_model')

        if active_model == 'sale.order' and active_id:
            order = self.env['sale.order'].browse(active_id)
            lines = []
            # Filter added: not line.is_delivery
            for line in order.order_line.filtered(lambda l: not l.is_delivery and not l.display_type):
                lines.append((0, 0, {
                    'order_line_id': line.id,
                }))
            res['line_ids'] = lines
        return res

    def confirm_refund_and_process(self):
        order = self.env['sale.order'].browse(self.env.context.get('active_id'))

        # Map the original order_line_id to the selected reason_id
        # Your custom refund_mataa_order() method will need to read this from the context
        # to apply the reasons to the newly created refund lines.
        line_reasons_mapping = {
            line.order_line_id.id: line.refund_reason_id.id 
            for line in self.line_ids if line.refund_reason_id
        }

        reason_data = {
            'refund_type': self.refund_type,
            'refund_description': self.refund_description,
            'refund_value_method': self.refund_value_method,
            'line_reasons': line_reasons_mapping,
        }

        action = order.with_context(refund_reasons=reason_data).refund_mataa_order()

        # --- DYNAMIC TICKET CREATION LOGIC ---
        if action and action.get('res_model') == 'sale.order' and action.get('res_id'):
            refund_order = self.env['sale.order'].browse(action['res_id'])

            company = self.env.company
            refund_team = company.refund_support_team_id
            refund_stage = company.refund_support_stage_id

            if not refund_team:
                raise UserError(_("Please configure the 'Refund Support Team' in the Order Management settings before creating a refund."))

            # Grab the reason names directly from the wizard lines for the ticket description
            reason_names = self.line_ids.mapped('refund_reason_id.name')
            reasons_str = ", ".join(filter(None, reason_names)) if reason_names else 'N/A'

            description_html = f"""
                <p>A new refund request has been created and requires review.</p>
                <strong> رقم الطلبية </strong> {order.name}<br/>
                <strong> رقم الاسترداد</strong> {refund_order.name}<br/>
                <br/>
                <strong>--  بيانات الاسترداد --</strong><br/>
                <strong> النوع</strong> {dict(self._fields['refund_type'].selection).get(self.refund_type)}<br/>
                <strong> الأسباب </strong> {reasons_str}<br/>
                <strong> القيمة </strong> {dict(self._fields['refund_value_method'].selection).get(self.refund_value_method)}<br/>
                <strong> الوصف </strong> {self.refund_description or 'N/A'}
            """

            ticket_vals = {
                'name': f'Refund Request for Order: {refund_order.name}',
                'team_id': refund_team.id,
                'description': description_html,
                'partner_id': refund_order.partner_id.id,
                'mataa_so_id': refund_order.id,
            }

            if refund_stage:
                ticket_vals['stage_id'] = refund_stage.id

            self.env['helpdesk.ticket'].create(ticket_vals)

        return action


class SaleRefundWizardLine(models.TransientModel):
    _name = 'sale.order.refund.reason.wizard.line'
    _description = 'Wizard Line for Sale Order Refund Reason'

    wizard_id = fields.Many2one('sale.order.refund.reason.wizard', required=True, ondelete='cascade')
    order_line_id = fields.Many2one('sale.order.line', required=True)
    
    # Displays the product name automatically
    product_id = fields.Many2one(related='order_line_id.product_id', string="Product", readonly=True)
    
    # The Many2one field for the refund reason per line
    refund_reason_id = fields.Many2one(
        'sale.order.reason', 
        string='السبب', 
        domain="[('reason_type', '=', 'refund')]"
    )