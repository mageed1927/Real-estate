from odoo import api, fields, models, tools, Command


class VendorPage(models.Model):
    _name = 'vendors.page'
    _auto = False

    name = fields.Many2one('res.partner', string="Vendor")
    product_sold_ids = fields.One2many('vendor.products.sold', 'vendor_id', string="Products sold")
    product_related_ids = fields.One2many('vendor.products.related', 'vendor_id', string="Products related")
    # product_blacklist_ids = fields.Many2many('product.vendor.blacklist', compute="get_blacklist_products")
    product_blacklist_count = fields.Integer(compute="get_blacklist_products")
    product_related_count = fields.Integer(compute="get_products_count")
    product_sold_count = fields.Integer(compute="get_products_count")
    min_amount = fields.Integer('Minimum amount')




    product_related_with_qty_count = fields.Integer(compute="_compute_product_related_with_qty_count",
                                                    string="Available Products Qty")
    product_price_adjustement_history_count = fields.Integer(compute="_compute_product_price_adjustement_history_count",
                                                             string="Prices adjustement history")

    mataa_on_hand_total = fields.Float(compute="_compute_mataa_on_hand_total", string="Mataa On Hand")
    vendor_tags = fields.Many2many('res.partner.category', related='name.category_id', string="Vendor Tags")

    def _compute_mataa_on_hand_total(self):
        for record in self:
            prev_count = record.mataa_on_hand_total
            locations = self.env.company.mataa_in_stock_locations_ids
            internal_locations = locations.filtered(lambda l: l.usage == 'internal')

            if internal_locations:
                self._cr.execute("""
                                 SELECT COALESCE(SUM(sq.quantity - sq.reserved_quantity), 0.0)
                                 FROM product_supplierinfo psi
                                          JOIN product_product pp ON pp.id = psi.product_id
                                          LEFT JOIN stock_quant sq ON sq.product_id = pp.id AND sq.location_id IN %s
                                 WHERE psi.partner_id = %s
                                 """, (tuple(internal_locations.ids), record.name.id))
                result = self._cr.fetchone()
                record.mataa_on_hand_total = result[0] if result else 0
            else:
                record.mataa_on_hand_total = 0
            if prev_count != record.mataa_on_hand_total:
                self._update_vendor_status(record)
            elif prev_count == record.mataa_on_hand_total and record.name.vendor_status != "partial":
                self._update_vendor_status(record)

    @api.depends('name')
    def get_blacklist_products(self):
        for record in self:
            blacklist_lines = self.env['product.vendor.blacklist'].search([('vendor_id', '=', record.name.id)])
            # record.product_blacklist_ids = [Command.link(line.id) for line in blacklist_lines]
            record.product_blacklist_count = len(blacklist_lines)

    def get_products_count(self):
        for record in self:
            record.product_related_count = len(record.product_related_ids)
            record.product_sold_count = len(record.product_sold_ids)

    def _compute_product_related_with_qty_count(self):
        for record in self:
            count = self.env['vendor.products.related'].search_count([
                ('vendor_id', '=', record.name.id),
                ('qty', '>', 0)
            ])
            prev_count = record.product_related_with_qty_count
            record.product_related_with_qty_count = count
            if prev_count != count:
                self._update_vendor_status(record)
            elif prev_count == count and record.name.vendor_status != "partial":
                self._update_vendor_status(record)

    def _compute_product_price_adjustement_history_count(self):
        for record in self:
            count = self.env['price.adjustement.history'].search_count([
                ('vendor_id', '=', record.name.id),
            ])
            record.product_price_adjustement_history_count = count

    def action_view_related_products(self):
        return {
            "type": "ir.actions.act_window",
            "res_model": "vendor.products.related",
            "domain": [('vendor_id', "=", self.name.id)],
            "context": {'default_vendor_id': self.name.id},
            "name": ("Related products for %s" % self.name.name),
            'view_mode': 'list',
        }


    def action_view_related_products_with_qty(self):
        return {
            "type": "ir.actions.act_window",
            "res_model": "vendor.products.related",
            "domain": [('vendor_id', "=", self.name.id), ('qty', '>', 0)],
            "context": {'default_vendor_id': self.name.id},
            "name": ("Related products with Qty for %s" % self.name.name),
            'view_mode': 'list',
        }

    def action_view_sold_products(self):
        return {
            "type": "ir.actions.act_window",
            "res_model": "vendor.products.sold",
            "domain": [('vendor_id', "=", self.name.id)],
            "context": {'default_vendor_id': self.name.id},
            "name": ("Products sold by %s" % self.name.name),
            'view_mode': 'list',
        }

    def action_view_price_adjustement_history(self):
        return {
            "type": "ir.actions.act_window",
            "res_model": "price.adjustement.history",
            "domain": [('vendor_id', "=", self.name.id)],
            "context": {'default_vendor_id': self.name.id, 'hide_vendor': 1},
            "name": ("Prices adjustement history for %s" % self.name.name),
            'view_mode': 'list,form',
        }

    def action_view_blacklist_products(self):
        return {
            "type": "ir.actions.act_window",
            "res_model": "product.vendor.blacklist",
            "domain": [('vendor_id', "=", self.name.id)],
            "context": {'default_vendor_id': self.name.id},
            "name": ("Blacklist Products for %s" % self.name.name),
            'view_mode': 'list,form',
        }

    def _update_vendor_status(self,record):
        partner = record.name
        if record.mataa_on_hand_total <= 0 and record.product_related_with_qty_count <= 0:
            if partner.vendor_status != "stopped":
                partner.write({"vendor_status": "stopped"})
        else:
            if partner.vendor_status != "ongoing":
                partner.write({"vendor_status": "ongoing"})            

    def _select(self):
        return """
            SELECT
                v.id as id,
                v.id as name,
                v.min_amount as min_amount
        """

    def _from(self):
        return """
            FROM res_partner AS v
        """

    def _join(self):
        return """"""

    def _where(self):
        return """
            WHERE
                supplier_rank > 0
        """

    def init(self):
        tools.drop_view_if_exists(self._cr, self._table)
        self._cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                %s
                %s
                %s
                %s
            )
        """ % (self._table, self._select(), self._from(), self._join(), self._where())
        )

    # def write(self, vals):
    #     if 'min_amount' in vals:
    #         self.partner_id.min_amount = vals['min_amount']
    #     return super(VendorPage, self).write(vals)


class VendorProductsSold(models.Model):
    _name = 'vendor.products.sold'
    _auto = False

    product_id = fields.Many2one('product.product', string="Product")
    product_tmpl_id = fields.Many2one(related='product_id.product_tmpl_id', string="Product Template", readonly=True)
    vendor_id = fields.Many2one('vendors.page', ondelete="cascade")
    qty = fields.Integer('Vendor Qty')
    mataa_qty = fields.Float(related="product_id.mataa_on_hand_qty")
    regular_price = fields.Float(related='product_id.regular_price', group_operator='max')
    sale_price = fields.Float(related='product_id.lst_price', group_operator='max')
    vendor_price = fields.Float(string='Vendor price', group_operator='max')
    sold_qty = fields.Integer('Sold qty')
    published = fields.Boolean('Published/Unpublished')
    is_synced = fields.Boolean()
    sale_orders = fields.Many2many('sale.order', compute="get_orders")
    purchase_orders = fields.Many2many('purchase.order', compute="get_orders")

    def get_orders(self):
        for record in self:
            s_orders = self.env['sale.order.line'].search([('product_id', '=', record.product_id.id)])
            record.sale_orders = [Command.link(so.id) for so in s_orders.mapped('order_id')]
            p_orders = self.env['purchase.order.line'].search([('product_id', '=', record.product_id.id)])
            record.purchase_orders = [Command.link(po.id) for po in p_orders.mapped('order_id')]

    def _select(self):
        return """
            SELECT DISTINCT
                sol.product_id as id,
                sol.product_id as product_id,
                sol.vendor_id as vendor_id,
                vendor.price as vendor_price,
                vendor.min_qty as qty,
                sum(sol.product_uom_qty) as sold_qty,
                vendor.published as published,
                prod.is_synced
            """

    def _from(self):
        return """
            FROM sale_order_line AS sol
        """

    def _join(self):
        return """
            JOIN product_supplierinfo vendor ON vendor.product_id = sol.product_id 
            JOIN product_product prod ON prod.id = sol.product_id 
        """

    def _where(self):
        return """"""

    def _groupby(self):
        return """
            GROUP BY
                sol.product_id,
                sol.vendor_id,
                vendor.price,
                vendor.min_qty,
                vendor.published,
                prod.is_synced
        """

    def init(self):
        tools.drop_view_if_exists(self._cr, self._table)
        self._cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                %s
                %s
                %s
                %s
                %s
            )
        """ % (self._table, self._select(), self._from(), self._join(), self._where(), self._groupby())
        )

    def show_sale_orders(self):
        return {
            "type": "ir.actions.act_window",
            "res_model": "sale.order",
            "domain": [('id', "in", self.sale_orders.ids)],
            "name": ("Sale orders related to %s" % self.product_id.display_name),
            'view_mode': 'list,form',
        }

    def show_purchase_orders(self):
        return {
            "type": "ir.actions.act_window",
            "res_model": "purchase.order",
            "domain": [('id', "in", self.purchase_orders.ids)],
            "name": ("Purchase orders related to %s" % self.product_id.display_name),
            'view_mode': 'list,form',
        }


class VendorProductsRelated(models.Model):
    _name = 'vendor.products.related'
    _auto = False

    product_id = fields.Many2one('product.product', string="Product")
    product_tmpl_id = fields.Many2one('product.template', string="Product Template")
    qty = fields.Integer('Vendor Qty')
    mataa_qty = fields.Float(related="product_id.mataa_on_hand_qty")
    price = fields.Float('Vendor Price', readonly=True, group_operator='max')
    regular_price = fields.Float(string='Regular Price', readonly=True, group_operator='max')
    sale_price = fields.Float(string='Sales Price', readonly=True, group_operator='max')
    cost = fields.Float(related='product_id.standard_price', string='Cost', readonly=True, group_operator='max')
    vendor_id = fields.Many2one('vendors.page', ondelete="cascade")
    published = fields.Boolean('Published/Unpublished')
    is_synced = fields.Boolean()
    sale_orders = fields.Many2many('sale.order', compute="get_orders")
    purchase_orders = fields.Many2many('purchase.order', compute="get_orders")
    last_sale_date = fields.Date(string="Last SO Date", readonly=True, group_operator='max')
    last_purchase_date = fields.Date(string="Last PO Date", readonly=True, group_operator='max')
    total_sold_qty = fields.Integer('Total Sold Qty')

    def get_orders(self):
        for record in self:
            s_orders = self.env['sale.order.line'].search([('product_id', '=', record.product_id.id)])
            record.sale_orders = [Command.link(so.id) for so in s_orders.mapped('order_id')]
            p_orders = self.env['purchase.order.line'].search([('product_id', '=', record.product_id.id)])
            record.purchase_orders = [Command.link(po.id) for po in p_orders.mapped('order_id')]

    def _select(self):
        return """
            SELECT
                info.id as id,
                info.product_id as product_id,
                pp.product_tmpl_id as product_tmpl_id,
                COALESCE(template_info.min_qty, info.min_qty) as qty,
                info.partner_id as vendor_id,
                COALESCE(template_info.price, info.price) as price,
                pt.regular_price as regular_price,
                pt.list_price as sale_price,
                info.published as published,
                info.is_synced as is_synced,
                template_dates.last_sale_date as last_sale_date,
                template_dates.last_purchase_date as last_purchase_date,
                COALESCE(sold.sold_qty, 0) as total_sold_qty

        """

    def _from(self):
        return """
            FROM product_supplierinfo AS info
        """

    def _join(self):
        return """
         JOIN product_product pp ON pp.id = info.product_id
         JOIN product_template pt ON pt.id = pp.product_tmpl_id
         LEFT JOIN product_supplierinfo template_info
            ON template_info.product_tmpl_id = pp.product_tmpl_id
            AND template_info.partner_id = info.partner_id
            AND template_info.product_id IS NULL
         LEFT JOIN (
            SELECT
                pp_dates.product_tmpl_id,
                MAX(pp_dates.last_sale_date) as last_sale_date,
                MAX(pp_dates.last_purchase_date) as last_purchase_date
            FROM product_product pp_dates
            GROUP BY pp_dates.product_tmpl_id
         ) template_dates ON template_dates.product_tmpl_id = pp.product_tmpl_id
         LEFT JOIN (
            SELECT
                sol.product_id,
                sum(sol.product_uom_qty) as sold_qty
            FROM sale_order_line sol
            GROUP BY sol.product_id
         ) sold ON sold.product_id = info.product_id
         """

    def _where(self):
        return """"""

    def init(self):
        tools.drop_view_if_exists(self._cr, self._table)
        self._cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                %s
                %s
                %s
                %s
            )
        """ % (self._table, self._select(), self._from(), self._join(), self._where())
        )

    def set_publish(self):
        self.write({
            'published': True
        })
        # Edit supplier_info
        self.env['product.supplierinfo'].browse(self.ids).write({
            'published': True
        })
        return

    def set_unpublish(self):
        self.write({
            'published': False
        })
        # Edit supplier_info
        self.env['product.supplierinfo'].browse(self.ids).write({
            'published': False
        })
        return

    def open_adjustement_wizard(self):
        self.env['adjustement.price.affected.field'].search([]).unlink()
        affected_fields = ['Sales price', 'Regular price', 'Vendor price']
        for field in affected_fields:
            self.env['adjustement.price.affected.field'].create({
                'name': field
            })
        return {
            'name': 'Price Adjustment',
            'type': 'ir.actions.act_window',
            'res_model': 'price.adjustment.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_product_ids': self.mapped('product_id').ids,  # Pass record IDs if needed
                'partner_id': self.vendor_id.name.id,
                'default_adjustment_type': 'increase'
            }
        }

    def show_sale_orders(self):
        return {
            "type": "ir.actions.act_window",
            "res_model": "sale.order",
            "domain": [('id', "in", self.sale_orders.ids)],
            "name": ("Sale orders related to %s" % self.product_id.display_name),
            'view_mode': 'list,form',
        }

    def show_purchase_orders(self):
        return {
            "type": "ir.actions.act_window",
            "res_model": "purchase.order",
            "domain": [('id', "in", self.purchase_orders.ids)],
            "name": ("Purchase orders related to %s" % self.product_id.display_name),
            'view_mode': 'list,form',
        }
