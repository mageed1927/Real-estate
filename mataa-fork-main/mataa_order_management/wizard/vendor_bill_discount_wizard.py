from odoo import models, fields, api, _
from odoo.exceptions import UserError


class VendorBillDiscountWizard(models.TransientModel):
    _name = 'vendor.bill.discount.wizard'
    _description = 'Retroactive Vendor Discount Wizard'

    move_id = fields.Many2one('account.move', string='Bill', required=True, readonly=True)


    journal_id = fields.Many2one(
        'account.journal',
        string='Journal',
        required=True,
        domain=[('type', 'in', ('purchase', 'general'))],
        help="Select the journal to record this discount entry."
    )

    line_ids = fields.One2many('vendor.bill.discount.line', 'wizard_id', string='Products')

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_id = self.env.context.get('active_id')
        if active_id:
            move = self.env['account.move'].browse(active_id)
            lines_data = []


            for line in move.invoice_line_ids.filtered(lambda l: l.product_id and l.display_type == 'product'):
                lines_data.append((0, 0, {
                    'move_line_id': line.id,
                    'product_id': line.product_id.id,
                    'quantity': line.quantity,
                    'discounted_qty': line.quantity,
                    'current_price': line.price_unit,
                    'discount_unit': 0.0,
                    'discount_amount': 0.0,
                }))
            res.update({
                'move_id': move.id,
                'line_ids': lines_data,
                'journal_id': move.journal_id.id,
            })
        return res

    def action_apply_discount(self):
        self.ensure_one()

        lines_to_process = self.line_ids.filtered(lambda l: l.discount_amount != 0)

        if not lines_to_process:
            raise UserError(_("Please enter a discount amount for at least one product."))

        total_discount = sum(lines_to_process.mapped('discount_amount'))


        move_lines = []


        move_lines.append((0, 0, {
            'name': f'Discount Ref: {self.move_id.name}',
            'partner_id': self.move_id.partner_id.id,
            'account_id': self.move_id.partner_id.property_account_payable_id.id,
            'debit': total_discount,
            'credit': 0.0,
        }))


        for line in lines_to_process:
            product = line.product_id


            if not product:
                raise UserError(_("Found a line with no product. Please verify your inputs."))

            valuation_account = product.categ_id.property_stock_valuation_account_id

            if not valuation_account:
                raise UserError(_(f"Product '{product.name}' category has no Stock Valuation Account defined!"))

            move_lines.append((0, 0, {
                'name': f'{product.name} - Disc. {self.move_id.name}',
                'account_id': valuation_account.id,
                'debit': -line.discount_amount if line.discount_amount < 0 else 0.0,
                'credit': line.discount_amount if line.discount_amount > 0 else 0.0,
                'product_id': product.id,
            }))


        discount_move = self.env['account.move'].create({
            'ref': f'Retro-Discount: {self.move_id.name}',
            'date': fields.Date.today(),
            'journal_id': self.journal_id.id,
            'move_type': 'entry',
            'line_ids': move_lines,
        })
        discount_move.action_post()

        bill_payable_lines = self.move_id.line_ids.filtered(
            lambda line: line.account_type == 'liability_payable' and not line.reconciled
        )


        discount_payable_lines = discount_move.line_ids.filtered(
            lambda line: line.account_type == 'liability_payable' and not line.reconciled
        )


        if bill_payable_lines and discount_payable_lines:
            (bill_payable_lines + discount_payable_lines).reconcile()


        for line in lines_to_process:
            self._create_valuation_layer(line.product_id, line.discount_amount, discount_move)

        return {'type': 'ir.actions.act_window_close'}

    def _create_valuation_layer(self, product, amount, related_move):
        """ create valuation layer and update the cost """
        if product.valuation != 'real_time':
            return

        svl = self.env['stock.valuation.layer'].create({
            'product_id': product.id,
            'value': -amount,
            'unit_cost': 0,
            'quantity': 0,
            'remaining_qty': 0,
            'description': f'Bill Discount: {self.move_id.name}',
            'account_move_id': related_move.id,
            'company_id': self.env.company.id,
        })


        current_qty = product.quantity_svl
        if current_qty > 0:

            total_value = sum(self.env['stock.valuation.layer'].search([
                ('product_id', '=', product.id),
                ('remaining_qty', '>', 0)
            ]).mapped('value'))


            new_cost = product.value_svl / current_qty
            product.sudo().write({'standard_price': new_cost})


class VendorBillDiscountLine(models.TransientModel):
    _name = 'vendor.bill.discount.line'
    _description = 'Discount Line'

    wizard_id = fields.Many2one('vendor.bill.discount.wizard')
    move_line_id = fields.Many2one('account.move.line', string='Bill Line')

    product_id = fields.Many2one('product.product', string='Product', readonly=True)
    quantity = fields.Float(string='Bill Qty', readonly=True)
    current_price = fields.Float(string='Unit Price', readonly=True)


    discounted_qty = fields.Float(string='Qty to Disc.', default=0.0,
                                  help="How many items are affected by this discount?")

    discount_unit = fields.Float(string='Disc./Unit',
                                 help="Discount amount per single unit")


    discount_amount = fields.Float(string='Total Discount', compute='_compute_discount_amount', store=True)

    @api.depends('discounted_qty', 'discount_unit')
    def _compute_discount_amount(self):
        for line in self:
            line.discount_amount = line.discounted_qty * line.discount_unit