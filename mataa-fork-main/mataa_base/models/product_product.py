# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    mataa_on_hand_qty = fields.Float(string="Mataa On Hand", compute='_compute_mataa_on_hand_qty', search='_search_mataa_on_hand_qty',
        compute_sudo=False, digits='Product Unit of Measure',store=False,)

    inhouse_qty = fields.Float(string="In-House Quantity",compute='_compute_inhouse_qty',compute_sudo=False,digits='Product Unit of Measure',store=False,)


    draft_reserved_qty = fields.Float(
        string='Draft Reserved',
        compute='_compute_draft_reserved_qty',
        digits='Product Unit of Measure',
        help='Quantity of this product that is reserved in draft quotations (Sale Orders).'
    )

    @api.depends('product_variant_ids.draft_reserved_qty')
    def _compute_draft_reserved_qty(self):
        for template in self:
            template.draft_reserved_qty = sum(template.product_variant_ids.mapped('draft_reserved_qty'))


    def _search_mataa_on_hand_qty(self, operator, value):
        domain = [('mataa_on_hand_qty', operator, value)]
        product_variant_query = self.env['product.product']._search(domain)
        return [('product_variant_ids', 'in', product_variant_query)]

    def _get_inhouse_qty(self):
        self.ensure_one()
        inhouse_location = self.env['stock.location'].search(
            [('complete_name', '=', 'WH/Stock/Inhouse')], limit=1
        )
        if not inhouse_location:
            return 0.0

        quants = self.env['stock.quant'].search([
            ('product_id', 'in', self.product_variant_ids.ids),
            ('location_id', '=', inhouse_location.id),
            ('on_hand', '=', True),
        ])
        return sum(quants.mapped('quantity')) - sum(quants.mapped('reserved_quantity'))

    def _get_free_qty_for_template(self):
        self.ensure_one()
        total = 0.0
        for pp in self.product_variant_ids:
            total += pp.get_free_qty()
        return total

    @api.depends(
        'product_variant_ids.qty_available',
        'product_variant_ids.virtual_available',
        'product_variant_ids.incoming_qty',
        'product_variant_ids.outgoing_qty',
    )
    def _compute_mataa_on_hand_qty(self):
        for pt in self:
            if pt.bom_count > 0:
                bom = self.env['mrp.bom'].search([
                    ('product_tmpl_id', '=', pt.id),
                    ('type', '=', 'phantom')
                ], limit=1)

                if bom:
                    min_qty = float('inf')
                    for line in bom.bom_line_ids:
                        if line.product_qty <= 0:
                            continue
                        component_qty = line.product_id.get_free_qty()
                        available_kits = component_qty / line.product_qty
                        min_qty = min(min_qty, available_kits)
                    pt.mataa_on_hand_qty = 0.0 if min_qty == float('inf') else min_qty
                else:
                    pt.mataa_on_hand_qty = 0.0
            else:
                pt.mataa_on_hand_qty = pt._get_free_qty_for_template()

            # pt._sync_replenishment_rules()
            pt._update_stock_auto_tags()

    def _compute_inhouse_qty(self):
        for pt in self:
            pt.inhouse_qty = pt._get_inhouse_qty()


    def _sync_replenishment_rules(self):
        location = self.env['stock.location'].search([('complete_name', '=', 'WH/Stock/Inhouse')], limit=1)
        buy_route = self.env.ref('purchase_stock.route_warehouse0_buy', raise_if_not_found=False)

        if not location or not buy_route:
            return

        orderpoint_model = self.env['stock.warehouse.orderpoint']

        for template in self:
            product_variants = template.product_variant_ids
            for variant in product_variants:
                existing_orderpoint = orderpoint_model.search([
                    ('product_id', '=', variant.id),
                    ('location_id', '=', location.id),
                ], limit=1)

                if not existing_orderpoint:
                    orderpoint_model.create({
                        'product_id': variant.id,
                        'location_id': location.id,
                        'warehouse_id': location.warehouse_id.id,
                        'product_min_qty': 2.0,
                        'product_max_qty': 6.0,
                        'route_id': buy_route.id,
                        'trigger': 'manual',
                        'company_id': template.company_id.id or self.env.company.id,
                    })

    def _update_stock_auto_tags(self):
        auto_tags = self.env.company.mataa_instock_products_auto_tags

        if not auto_tags:
            return

        for product in self:
            current_tags = product.product_tag_ids

            if product.mataa_on_hand_qty > 0:
                tags_to_add = auto_tags - current_tags
                if tags_to_add:
                    product.product_tag_ids = [(4, tag.id) for tag in tags_to_add]
            else:
                tags_to_remove = auto_tags & current_tags
                if tags_to_remove:
                    product.product_tag_ids = [(3, tag.id) for tag in tags_to_remove]

    def action_update_mataa_quantity_on_hand(self):
        advanced_option_groups = [
            'stock.group_stock_multi_locations',
            'stock.group_tracking_owner',
            'stock.group_tracking_lot'
        ]
        if (self.env.user.user_has_groups(','.join(advanced_option_groups))) or self.tracking != 'none':
            return self.with_context(mataa_on_hand=True).action_open_quants()
        else:
            default_product_id = self.env.context.get('default_product_id',
                                                      len(self.product_variant_ids) == 1 and self.product_variant_id.id)
            action = self.env["ir.actions.actions"]._for_xml_id("stock.action_change_product_quantity")
            action['context'] = dict(
                self.env.context,
                default_product_id=default_product_id,
                mataa_on_hand=True,
                default_product_tmpl_id=self.id
            )
            return action

    def action_open_quants(self):
        action = super(ProductTemplate, self).action_open_quants()

        if self._context.get('mataa_on_hand'):
            location_ids = self.env.company.mataa_in_stock_locations_ids
            if location_ids:
                domain = action.get('domain', [])
                domain.append(('location_id', 'in', location_ids.ids))
        return action

class ProductProduct(models.Model):
    _inherit = 'product.product'

    mataa_variant_seller_ids = fields.One2many('product.supplierinfo', 'product_id')

    sale_line_ids = fields.One2many('sale.order.line', 'product_id', string="Sale Lines")

    was_in_house = fields.Boolean(copy=False, help="True if the product is mataa-in-house at least once")
    mataa_on_hand_qty = fields.Float(string="Mataa On Hand", compute='_compute_mataa_on_hand_qty',
                                     search='_search_mataa_in_house_qty', digits='Product Unit of Measure', compute_sudo=False)

    last_purchase_date = fields.Date(
        string='Last Purchase Date',
        compute='_compute_last_purchase_date',
        group_operator='max',
        store=True,
    )

    last_sale_date = fields.Date(
        string='Last Sale Date',
        compute='_compute_last_sale_date',
        group_operator='max',
        store=True,
    )

    draft_reserved_qty = fields.Float(
        string='Draft Reserved',
        compute='_compute_draft_reserved_qty',
        digits='Product Unit of Measure',
    )

    @api.depends('stock_move_ids.state', 'stock_move_ids.product_uom_qty')
    def _compute_draft_reserved_qty(self):
        for product in self:
            draft_moves = self.env['stock.move'].search([
                ('product_id', '=', product.id),
                ('state', 'in', ['confirmed', 'partially_available', 'assigned']),
                ('picking_id', '=', False),
                ('sale_line_id', '!=', False),
                ('sale_line_id.order_id.state', 'in', ['draft', 'sent'])
            ])
            product.draft_reserved_qty = sum(draft_moves.mapped('product_uom_qty'))

    @api.depends('purchase_order_line_ids.order_id.date_order', 'purchase_order_line_ids.order_id.state')
    def _compute_last_purchase_date(self):
        for product in self:
            po_lines = product.purchase_order_line_ids.filtered(
                lambda l: l.order_id.state in ['purchase', 'done']
            )

            if po_lines:
                latest_line = po_lines.sorted(key=lambda line: line.order_id.date_order, reverse=True)[0]
                product.last_purchase_date = latest_line.order_id.date_order
            else:
                product.last_purchase_date = False

    @api.depends('sale_line_ids.order_id.date_order', 'sale_line_ids.order_id.state')
    def _compute_last_sale_date(self):
        for product in self:
            so_lines = product.sale_line_ids.filtered(
                lambda line: line.order_id.state in ['sale', 'done']
            )

            if so_lines:
                latest_line = so_lines.sorted(key=lambda line: line.order_id.date_order, reverse=True)[0]
                product.last_sale_date = latest_line.order_id.date_order
            else:
                product.last_sale_date = False

    def _search_mataa_in_house_qty(self, operator, value):
        location_ids = self.env.company.mataa_in_stock_locations_ids.ids
        return self.with_context(location=location_ids)._search_product_quantity(operator, value, 'qty_available')

    @api.depends('stock_move_ids.product_qty', 'stock_move_ids.state', 'stock_move_ids.quantity')
    def _compute_mataa_on_hand_qty(self):
        for product in self:
            product.mataa_on_hand_qty = product.get_free_qty()

    def get_free_qty(self):
        self.ensure_one()
        product = self._origin or self
        if not product.id or not isinstance(product.id, int):
            return 0.0

        bom = self.env['mrp.bom'].search([('product_tmpl_id', '=', product.product_tmpl_id.id), ('type', '=', 'phantom')], limit=1)
        if bom:
            min_qty = float('inf')
            boms, lines = bom.explode(product, 1)
            for line, line_data in lines:
                if line.product_qty <=0:
                    continue
                component_free_qty = line.product_id.get_free_qty()
                if line_data['qty'] > 0:
                    kits_from_component = component_free_qty / line.product_qty
                    min_qty = min(min_qty, kits_from_component)
            return 0.0 if min_qty == float('inf') else min_qty

        free_qty = self.free_qty
        location_ids = self.env.company.mataa_in_stock_locations_ids
        if location_ids:
            sq_ids = self.env['stock.quant'].search([('product_id', '=', product.id),
                                                     ("location_id.usage", "=", "internal"),
                                                     ("on_hand", "=", True),
                                                     ("location_id.id", "in", location_ids.ids),
                                                     ])
            stock_moves = self.env['stock.move'].search([
                ('product_id', '=', product.id),
                ('state', 'in', ['confirmed', 'partially_available', 'assigned']),
                ('picking_id', '!=', False),
                ('picking_type_id', '=', 3)
            ])
            stock_demand = sum(stock_moves.mapped('quantity'))
            free_qty = sum(sq_ids.mapped('quantity')) - stock_demand

        draft_moves = self.env['stock.move'].search([
            ('product_id', '=', self.id),
            ('state', 'in', ['confirmed', 'partially_available', 'assigned']),
            ('picking_id', '=', False),
            ('sale_line_id', '!=', False),
            ('sale_line_id.order_id.state', 'in', ['draft', 'sent'])
        ])

        draft_reserved_qty = sum(draft_moves.mapped('product_uom_qty'))

        free_qty -= draft_reserved_qty

        return free_qty

    def action_update_mataa_quantity_on_hand(self):
        return self.product_tmpl_id.with_context(default_product_id=self.id,
                                                 mataa_on_hand=True,
                                                 create=True).action_update_mataa_quantity_on_hand()

    def action_open_quants(self):
        action = super(ProductProduct, self).action_open_quants()

        if self._context.get('mataa_on_hand'):
            location_ids = self.env.company.mataa_in_stock_locations_ids
            if location_ids:
                domain = action.get('domain', [])
                domain.append(('location_id', 'in', location_ids.ids))
        return action

    def _cron_compute_was_inhouse(self):
        location_ids = self.env.company.mataa_in_stock_locations_ids
        to_inhouse_sml_ids = self.env['stock.move.line'].search([]).filtered(lambda l: l.location_dest_id.id in location_ids.ids)
        to_inhouse_sml_ids.mapped('product_id').with_context(pre_sync=True).write({'was_in_house': True})
