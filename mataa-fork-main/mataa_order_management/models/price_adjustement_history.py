from odoo import api, fields, models


class PriceAdjustementHistory(models.Model):
    _name = 'price.adjustement.history'
    _description = 'Vendors page → price adjustement history'

    name = fields.Char(string="Reference")
    vendor_id = fields.Many2one('res.partner', string="Vendor")
    date = fields.Datetime('Time', default=lambda self: fields.Datetime.now())
    expiration_date = fields.Datetime('Expiration Time')
    history_lines = fields.One2many('price.adjustement.history.line', 'history_id')
    note = fields.Text('Note')
    active = fields.Boolean('Active', default=True)
    adjustment_method = fields.Selection(
        selection=[('fixed', 'Fixed Amount'), ('percentage', 'Percentage')], string='Adjustment Method')
    adjustment_type = fields.Selection(
        selection=[('increase', 'Increase'), ('decrease', 'Decrease')], string='Adjustment Type')
    adjustment_value = fields.Float(string='Adjustment Value')
    base_amount = fields.Selection([('sales_price', 'Sales price'), ('regular_price', 'Regular price'),
                                    ('vendor_price', 'Vendor price')])

    start_date = fields.Datetime('Start Date')
    product_tag_ids = fields.Many2many('product.tag', string="Applied Tags")
    is_started = fields.Boolean('Is Started', default=False, copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name', False):
                vals['name'] = self.env['ir.sequence'].next_by_code('price.adjustement.history')
        return super(PriceAdjustementHistory, self).create(vals_list)

    def action_redo_prices(self):
        supplierinfo_obj = self.env['product.supplierinfo']

        if self.product_tag_ids:
            product_ids = self.history_lines.mapped('product_id')
            product_ids.write({'product_tag_ids': [(3, tag.id) for tag in self.product_tag_ids]})

        for line in self.history_lines:
            supplierinfo = supplierinfo_obj.search([('product_id', '=', line.product_id.id),
                                                    ('partner_id', '=', line.history_id.vendor_id.id)], limit=1)
            if line.affected_field == 'sales_price':
                line.product_id.with_context(skip_vendor_price_check=True).write({
                    'lst_price': line.price
                })
            elif line.affected_field == 'regular_price':
                line.product_id.with_context(skip_vendor_price_check=True).write({
                    'regular_price': line.price
                })
            elif line.affected_field == 'vendor_price':
                supplierinfo.with_context(skip_vendor_price_check=True).write({
                    'price': line.price
                })
        self.active = False

    @api.model
    def redo_prices_automatically(self):
        now = fields.Datetime.now()
        prices_history = self.search([('active', '=', True), ('expiration_date', '<=', now)])
        for history in prices_history:
            history.action_redo_prices()

    def apply_scheduled_prices(self):
        """
        This method is called by a cron job.
        It finds price adjustments that are due to start, applies them,
        adds the tag, and marks them as started.
        """
        adjustments_to_start = self.search([
            ('active', '=', True),
            ('is_started', '=', False),
            ('start_date', '<=', fields.Datetime.now())
        ])

        supplierinfo_obj = self.env['product.supplierinfo']

        for history in adjustments_to_start:
            products = history.history_lines.mapped('product_id')

            if history.product_tag_ids:
                products.write({'product_tag_ids': [(4, tag.id) for tag in history.product_tag_ids]})

            for product in products:
                supplierinfo = supplierinfo_obj.search([('product_id', '=', product.id),
                                                        ('partner_id', '=', history.vendor_id.id)], limit=1)
                regular_price = product.regular_price
                sale_price = product.lst_price
                vendor_price = supplierinfo.price


                base_amount = regular_price
                if history.base_amount == 'sales_price':
                    base_amount = sale_price
                elif history.base_amount == 'vendor_price':
                    base_amount = vendor_price


                for line in history.history_lines.filtered(lambda l: l.product_id == product):
                    current_price = line.price

                    if history.adjustment_method == 'fixed':
                        amount_to_add = history.adjustment_value
                    else:
                        amount_to_add = history.adjustment_value / 100 * current_price

                    if history.adjustment_type == 'increase':
                        new_price = round(current_price + amount_to_add)
                    else:
                        new_price = round(current_price - amount_to_add)


                    if line.affected_field == 'sales_price':
                        product.with_context(skip_vendor_price_check=True).write({'lst_price': new_price})
                    elif line.affected_field == 'regular_price':
                        product.with_context(skip_vendor_price_check=True).write({'regular_price': new_price})

                        product.product_tmpl_id.with_context(skip_vendor_price_check=True).write(
                            {'regular_price': new_price})
                    elif line.affected_field == 'vendor_price':
                        supplierinfo.with_context(skip_vendor_price_check=True).write({'price': new_price})


            history.is_started = True

    def action_start_manually(self):
        """
        Manually starts a specific price adjustment promotion.
        This is triggered by a button on the form view.
        """
        for history in self:
            if not history.active or history.is_started:

                continue


            products = history.history_lines.mapped('product_id')
            supplierinfo_obj = self.env['product.supplierinfo']

            if history.product_tag_ids:
                products.write({'product_tag_ids': [(4, tag.id) for tag in history.product_tag_ids]})


            for product in products:
                supplierinfo = supplierinfo_obj.search([('product_id', '=', product.id),
                                                        ('partner_id', '=', history.vendor_id.id)], limit=1)

                for line in history.history_lines.filtered(lambda l: l.product_id == product):
                    current_price = line.price

                    if history.adjustment_method == 'fixed':
                        amount_to_add = history.adjustment_value
                    else:
                        amount_to_add = history.adjustment_value / 100 * current_price

                    if history.adjustment_type == 'increase':
                        new_price = round(current_price + amount_to_add)
                    else:
                        new_price = round(current_price - amount_to_add)

                    if line.affected_field == 'sales_price':
                        product.with_context(skip_vendor_price_check=True).write({'lst_price': new_price})
                    elif line.affected_field == 'regular_price':
                        product.with_context(skip_vendor_price_check=True).write({'regular_price': new_price})
                        product.product_tmpl_id.with_context(skip_vendor_price_check=True).write(
                            {'regular_price': new_price})
                    elif line.affected_field == 'vendor_price':
                        supplierinfo.with_context(skip_vendor_price_check=True).write({'price': new_price})

            history.is_started = True


class PriceAdjustementHistoryLine(models.Model):
    _name = 'price.adjustement.history.line'
    _description = 'Vendors page → price adjustement history'

    history_id = fields.Many2one('price.adjustement.history', ondelete="cascade")
    product_id = fields.Many2one('product.product', string="Product")
    price = fields.Float('Price')
    affected_field = fields.Selection([('sales_price', 'Sales price'), ('regular_price', 'Regular price'),
                                       ('vendor_price', 'Vendor price')], string='Affected field')
