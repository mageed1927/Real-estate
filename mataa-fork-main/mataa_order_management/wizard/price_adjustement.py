
from odoo import models, fields, api
from datetime import datetime, time
from odoo.exceptions import UserError


class PriceAdjustmentWizard(models.TransientModel):
    _name = 'price.adjustment.wizard'
    _description = 'Price Adjustment Wizard'

    # Field 1: Increase/Decrease selection
    adjustment_type = fields.Selection(
        selection=[
            ('increase', 'Increase'),
            ('decrease', 'Decrease')
        ],
        string='Adjustment Type',
        required=True,
        default='increase'
    )

    # Field 2: Adjustment Method (Fixed/Percentage)
    adjustment_method = fields.Selection(
        selection=[
            ('fixed', 'Fixed Amount'),
            ('percentage', 'Percentage')
        ],
        string='Adjustment Method',
        required=True,
        default='fixed'
    )

    # Field 3: Float value (amount or percentage)
    adjustment_value = fields.Float(
        string='Adjustment Value',
        required=True,
        default=0.0
    )

    # Optional: Dynamic string for adjustment value based on method
    adjustment_value_label = fields.Char(
        string='Value Label',
        compute='_compute_adjustment_value_label'
    )

    discount_reason_id = fields.Many2one(
        'price.adjustment.reason',
        string='Discount Reason',
        required=True,
        domain="[('active', '=', True)]"
    )
    discount_description = fields.Text(string='Description')

    fields_affected = fields.Many2many('adjustement.price.affected.field', string="Affected fields")
    with_template = fields.Boolean(default=True)
    show_with_template = fields.Boolean(compute="get_show_with_template")
    base_amount = fields.Many2one('adjustement.price.affected.field')
    expiration_date = fields.Datetime('Expiration date')
    note = fields.Text('Note')

    start_date = fields.Datetime('Start Date', default=fields.Datetime.now)
    product_tag_ids = fields.Many2many('product.tag', string="Tags to Apply",
                                       help="These tags will be added to the products and removed when the promotion expires.")

    @api.depends('fields_affected')
    def get_show_with_template(self):
        for record in self:
            if record.fields_affected and 'Regular price' in record.fields_affected.mapped('name'):
                record.show_with_template = True
            else:
                record.show_with_template = False

    @api.depends('adjustment_method')
    def _compute_adjustment_value_label(self):
        for record in self:
            if record.adjustment_method == 'percentage':
                record.adjustment_value_label = 'Percentage (%)'
            else:
                record.adjustment_value_label = 'Amount'

    # Action buttons
    def action_apply(self):
        # Add your logic here for applying the adjustment
        self.ensure_one()
        products = self.env['product.product'].browse(self.env.context.get('default_product_ids'))
        partner_id = self.env.context.get('partner_id', False)
        # Save prices before proceed
        self.save_prices(products, partner_id)
        if self.start_date and self.start_date > datetime.now():
            return {'type': 'ir.actions.act_window_close'}

        update_vals = {
            'last_discount_reason_id': self.discount_reason_id.id,
            'last_discount_description': self.discount_description,
        }

        for product in products:
            if self.product_tag_ids:
                product.write({'product_tag_ids': [(4, tag.id) for tag in self.product_tag_ids]})

            supplierinfo_obj = self.env['product.supplierinfo']

            supplierinfo = supplierinfo_obj.search([('product_id', '=', product.id),
                                                    ('partner_id', '=', partner_id)], limit=1)
            regular_price = product.regular_price
            tmpl_regular_price = product.product_tmpl_id.regular_price
            sale_price = product.lst_price
            vendor_price = supplierinfo.price
            base_amount = self.get_base_amount(regular_price, sale_price, vendor_price)
            tmpl_base_amount = base_amount
            for field in self.fields_affected:
                if field.name == 'Regular price':
                    if self.adjustment_method == 'fixed':
                        amount_to_add = self.adjustment_value
                        tmpl_amount_to_add = self.adjustment_value
                        base_amount = product.regular_price
                        tmpl_base_amount = product.product_tmpl_id.regular_price
                    else:
                        amount_to_add = self.adjustment_value / 100 * base_amount
                        tmpl_amount_to_add = self.adjustment_value / 100 * base_amount

                    if self.adjustment_type == 'increase':
                        product.with_context(skip_vendor_price_check=True).write({
                            'regular_price': round(base_amount + amount_to_add)
                        })
                        if self.with_template:
                            product.product_tmpl_id.with_context(skip_vendor_price_check=True).write({
                                'regular_price': round(tmpl_base_amount + tmpl_amount_to_add)
                            })
                    else:
                        product.with_context(skip_vendor_price_check=True).write({
                            'regular_price': round(product.regular_price - amount_to_add)
                        })
                        if self.with_template:
                            product.product_tmpl_id.with_context(skip_vendor_price_check=True).write({
                                'regular_price': round(product.product_tmpl_id.regular_price - tmpl_amount_to_add)
                            })
                elif field.name == 'Sales price':
                    if self.adjustment_method == 'fixed':
                        amount_to_add = self.adjustment_value
                        base_amount = product.lst_price
                    else:
                        amount_to_add = self.adjustment_value/100 * base_amount

                    if self.adjustment_type == 'increase':
                        product.with_context(skip_vendor_price_check=True).write({
                            'lst_price': round(base_amount + amount_to_add)
                        })
                    else:
                        product.with_context(skip_vendor_price_check=True).write({
                            'lst_price': round(base_amount - amount_to_add)
                        })
                elif field.name == 'Vendor price':
                    if self.adjustment_method == 'fixed':
                        amount_to_add = self.adjustment_value
                        base_amount = supplierinfo.price
                    else:
                        amount_to_add = self.adjustment_value/100 * base_amount

                    if self.adjustment_type == 'increase':
                        new_vendor_price = base_amount + amount_to_add
                    else:
                        new_vendor_price = base_amount - amount_to_add
                    supplierinfo.with_context(skip_vendor_price_check=True).write({
                        'price': round(new_vendor_price)
                    })

            product.write(update_vals)
            if self.with_template:
                product.product_tmpl_id.write(update_vals)

            supplierinfo_obj.check_prices(product, supplierinfo.price, product.lst_price, product.regular_price)

            history_to_start = self.env['price.adjustement.history'].search([
                ('start_date', '=', self.start_date),
                ('vendor_id', '=', partner_id),
                ('product_tag_ids', 'in', self.product_tag_ids.ids)
            ], order='create_date desc', limit=1)
            if history_to_start:
                history_to_start.is_started = True

        return {'type': 'ir.actions.act_window_close'}

    def get_base_amount(self, regular_price, sale_price, vendor_price):
        if not self.base_amount:
            return regular_price or sale_price or vendor_price
        if self.base_amount.name == 'Regular price':
            return regular_price
        elif self.base_amount.name == 'Sales price':
            return sale_price
        else:
            return vendor_price

    def save_prices(self, products, partner_id):
        supplierinfo_obj = self.env['product.supplierinfo']

        base_amount_key = False
        if self.base_amount:
            base_amount_key = self.base_amount.name.lower().strip().replace(' ', '_')

        price_history = self.env['price.adjustement.history'].create({
            'vendor_id': partner_id,
            'adjustment_method': self.adjustment_method,
            'adjustment_type': self.adjustment_type,
            'adjustment_value': self.adjustment_value,
            'start_date': self.start_date,
            'base_amount': base_amount_key,
            #'base_amount': self.base_amount if self.base_amount else False,
            'expiration_date': self.expiration_date,
            'product_tag_ids': [(6, 0, self.product_tag_ids.ids)],
            'note': self.note
        })
        for product in products:
            supplierinfo = supplierinfo_obj.search([('product_id', '=', product.id),
                                                    ('partner_id', '=', partner_id)], limit=1)

            for field in self.fields_affected:
                price = 0
                if field.name == 'Regular price':
                    price = product.regular_price
                elif field.name == 'Sales price':
                    price = product.lst_price
                elif field.name == 'Vendor price' and supplierinfo:
                    price = supplierinfo.price
                if price:
                    self.env['price.adjustement.history.line'].create({
                        'affected_field': field.name.lower().strip().replace(' ', '_'),
                        'product_id': product.id,
                        'price': price,
                        'history_id': price_history.id
                    })


class adjustement_price_affected_field(models.TransientModel):
    _name = "adjustement.price.affected.field"

    name = fields.Char('field')
