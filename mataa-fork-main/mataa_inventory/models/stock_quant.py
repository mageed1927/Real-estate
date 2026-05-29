import logging
from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)


class StockQuant(models.Model):
    _inherit = 'stock.quant'

    is_located = fields.Boolean(string="Is Located", default=False)
    assigned_by = fields.Many2one('res.users', string='Assigned By', readonly=True)
    product_barcode = fields.Char(
        string="Barcode",
        related='product_id.barcode',
        readonly=True,
    )

    @api.model
    def get_inventory_user_id(self):
        return int(self.env['ir.config_parameter'].sudo().get_param(
            'mataa_inventory.inventory_user_id', '0'
        ))

    def action_validate(self):
        res = super().action_validate()
        self.write({'is_located': False})
        return res

    def action_clear_inventory_quantity(self):
        res = super().action_clear_inventory_quantity()
        self.write({'assigned_by': False})
        return res

    def _get_stock_barcode_data(self):
        locations = self.env['stock.location']
        company_id = self.env.company.id
        package_types = self.env['stock.package.type']
        if not self:
            if self.env.user.has_group('stock.group_stock_multi_locations'):
                locations = self.env['stock.location'].search([('usage', 'in', ['internal', 'transit']), ('company_id', '=', company_id)], order='id')
            else:
                locations = self.env['stock.warehouse'].search([('company_id', '=', company_id)], limit=1).lot_stock_id
            domain = [
                ('location_id', 'in', locations.ids),
                ('inventory_date', '<=', fields.Date.today()),
                '|',
                ('user_id', '=', self.env.user.id),
                ('assigned_by', '=', self.env.user.id)
            ]
            self = self.env['stock.quant'].search(
                domain,
                order='inventory_quantity_set desc, id',
            )
            if self.env.user.has_group('stock.group_tracking_lot'):
                package_types = package_types.search([])

        data = self.with_context(display_default_code=False, barcode_view=True).get_stock_barcode_data_records()
        if locations:
            data["records"]["stock.location"] = locations.read(locations._get_fields_stock_barcode(), load=False)
        if package_types:
            data["records"]["stock.package.type"] = package_types.read(package_types._get_fields_stock_barcode(), load=False)
        data['line_view_id'] = self.env.ref('stock_barcode.stock_quant_barcode').id
        return data

    @api.model
    def fetch_quant_by_barcode(self, barcode, location_id=False):
        product = self.env['product.product'].search([('barcode', '=', barcode)], limit=1)
        if not product:
            packaging = self.env['product.packaging'].search([('barcode', '=', barcode)], limit=1)
            product = packaging.product_id
        if not product:
            return False

        domain = [
            ('product_id', '=', product.id),
            ('inventory_date', '<=', fields.Date.today()),
            '|',
            ('user_id', '=', self.env.user.id),
            ('assigned_by', '=', self.env.user.id),
        ]
        if location_id:
            domain.append(('location_id', '=', location_id))

        quants = self.search(domain, order='inventory_quantity_set, id')
        if not quants:
            return False
        return quants.with_context(
            display_default_code=False,
            barcode_view=True,
        ).get_stock_barcode_data_records()

    @api.model
    def _get_fields_stock_barcode(self):
        fields = super()._get_fields_stock_barcode()
        fields.append('is_located')
        fields.append('assigned_by')
        return fields

    @api.model
    def _barcode_inventory_context(self):
        return {
            'inventory_mode': True,
            'skip_mataa_quant_sync': True,
        }

    @api.model
    def _get_destination_quant_key(self, product_id, location_id, package_id):
        return (product_id, location_id, package_id or False)

    @api.model
    def _get_destination_quants_map(self, buffer_data, location_id, package_id):
        product_ids = {line['product_id'] for line in buffer_data if line.get('product_id')}
        if not product_ids:
            return {}

        package_ids = [package_id or False]
        if package_id:
            package_ids.append(False)

        destination_quants = self.env['stock.quant'].search([
            ('product_id', 'in', list(product_ids)),
            ('location_id', '=', location_id),
            ('package_id', 'in', package_ids),
        ])
        return {
            self._get_destination_quant_key(quant.product_id.id, quant.location_id.id, quant.package_id.id): quant
            for quant in destination_quants
        }

    @api.model
    def _get_or_search_destination_quant(self, product_id, location_id, package_id, destination_quants_map):
        key = self._get_destination_quant_key(product_id, location_id, package_id)
        quant = destination_quants_map.get(key)
        if quant:
            return quant

        quant = self.env['stock.quant'].search([
            ('product_id', '=', product_id),
            ('location_id', '=', location_id),
            ('package_id', '=', package_id or False),
        ], limit=1)
        if quant:
            destination_quants_map[key] = quant
        return quant

    @api.model
    def _refresh_quant_state(self, quant):
        if quant:
            quant.invalidate_recordset([
                'quantity',
                'inventory_quantity',
                'inventory_quantity_set',
                'inventory_diff_quantity',
                'user_id',
                'assigned_by',
                'is_located',
            ])
        return quant

    def _process_match_logic(self, quant, line, location_id, package_id, existing_quant=False):
        quant = self._refresh_quant_state(quant)
        existing_quant = self._refresh_quant_state(existing_quant) or self.env['stock.quant']

        if existing_quant:
            if not existing_quant.user_id:
                inventory_qty = existing_quant.quantity
                is_located = True
            else:   
                inventory_qty = existing_quant.inventory_quantity + line['quantity']
                is_located = existing_quant.is_located
            existing_quant.with_context(**self._barcode_inventory_context()).write({
                'user_id': line['user_id'],
                'assigned_by': line['assigned_by'],
                'inventory_date': fields.Date.today(),
                'inventory_quantity' : inventory_qty,
                'is_located': is_located,
                'inventory_quantity_set': True,
            })
            quant.with_context(**self._barcode_inventory_context()).write({
                'inventory_quantity': 0,
                'user_id': False,
                'assigned_by': False,
            })

    def _process_shortage_logic(self, quant, line, location_id, package_id, existing_quant=False):
        quant = self._refresh_quant_state(quant)
        existing_quant = self._refresh_quant_state(existing_quant) or self.env['stock.quant']

        if location_id != line['location_id'] or package_id != line['package_id']:
            if existing_quant:
                if not existing_quant.user_id:
                    inventory_qty = existing_quant.quantity
                    is_located = True
                else:
                    inventory_qty = existing_quant.inventory_quantity + line['quantity']
                    is_located = existing_quant.is_located
                existing_quant.with_context(**self._barcode_inventory_context()).write({
                    'inventory_quantity': inventory_qty,
                    'user_id': line['user_id'],
                    'assigned_by': line['assigned_by'],
                    'inventory_quantity_set': True,
                    'inventory_date': fields.Date.today(),
                    'is_located': is_located,
                })
                quant.with_context(**self._barcode_inventory_context()).write({
                    'inventory_quantity': 0, 
                    'inventory_quantity_set': False
                    })
        else:
            if existing_quant:
                existing_quant.with_context(**self._barcode_inventory_context()).write({
                    'user_id': line['user_id'],
                    'assigned_by': line['assigned_by'],
                    'inventory_date': fields.Date.today(),
                })
            quant.with_context(**self._barcode_inventory_context()).write({
                'is_located': True,
                'inventory_quantity_set': True,
            })

    def _process_surplus_logic(self, quant, line, location_id, package_id, quantity, diff_qty, quant_quantity, inventory_user_id, existing_quant=False):
        quant = self._refresh_quant_state(quant)
        existing_quant = self._refresh_quant_state(existing_quant) or self.env['stock.quant']

        if quant_quantity>0:
            if existing_quant:
                if not existing_quant.user_id:
                    inventory_qty = existing_quant.quantity + diff_qty
                    is_located = True
                else:   
                    inventory_qty = existing_quant.inventory_quantity + quantity
                    is_located = existing_quant.is_located
                existing_quant.with_context(**self._barcode_inventory_context()).write({
                    'inventory_quantity' : inventory_qty,
                    'user_id': line['user_id'],
                    'assigned_by': line['assigned_by'],
                    'inventory_quantity_set': True,
                    'inventory_date': fields.Date.today(),
                    'is_located': is_located,
                })
            if existing_quant:
                quant.with_context(**self._barcode_inventory_context()).write({
                    'inventory_quantity': 0,
                    'user_id': False,
                    'assigned_by': False,
                })
        else:
            if existing_quant:
                if not existing_quant.user_id:
                    inventory_qty = existing_quant.quantity
                    is_located = True
                else:   
                    inventory_qty = existing_quant.inventory_quantity
                    is_located = existing_quant.is_located
                inventory_qty += quantity

                existing_quant.with_context(**self._barcode_inventory_context()).write({
                    'inventory_quantity' : inventory_qty,
                    'user_id': line['user_id'],
                    'assigned_by': inventory_user_id,
                    'inventory_quantity_set': True,
                    'inventory_date': fields.Date.today(),
                    'is_located': is_located,
                })
                quant.with_context(**self._barcode_inventory_context()).write({
                    'inventory_quantity': 0, 
                    'inventory_quantity_set': False,
                    'user_id': False,
                    'assigned_by': False,
                    })
            else:
                quant.with_context(skip_mataa_quant_sync=True).write({
                    'location_id': location_id,
                    'package_id': package_id or False,
                    'is_located': True,
                    'assigned_by': inventory_user_id,
                })

    @api.model
    def action_process_barcode_buffer(self, buffer_data, location_id, package_id=False):
        if not buffer_data:
            return True

        inventory_user_id = self.get_inventory_user_id()
        source_quants = {
            quant.id: quant
            for quant in self.env['stock.quant'].browse([line['quant_id'] for line in buffer_data]).exists()
        }
        destination_quants_map = self._get_destination_quants_map(buffer_data, location_id, package_id)

        for line in buffer_data:
            quant = source_quants.get(line['quant_id'])
            if not quant or quant.is_located:
                continue

            if quant.inventory_diff_quantity == 0:
                if location_id == line['location_id'] and package_id == line['package_id']:
                    quant.with_context(**self._barcode_inventory_context()).write({
                        'is_located': True,
                    })
                    continue
                if self.move(line, location_id, package_id):
                    destination_quant = self._get_or_search_destination_quant(
                        line['product_id'], location_id, package_id, destination_quants_map,
                    )
                    self._process_match_logic(quant, line, location_id, package_id, destination_quant)
        

            elif quant.inventory_diff_quantity < 0:
                if location_id != line['location_id'] or package_id != line['package_id']:
                    self.move(line, location_id, package_id)
                else:
                    line['quantity'] = abs(quant.inventory_diff_quantity)
                    self.move(line, location_id, False)
                
                shortage_quant = self._get_or_search_destination_quant(
                    line['product_id'], location_id, package_id, destination_quants_map,
                )
                if location_id == line['location_id'] and package_id == line['package_id']:
                    shortage_quant = self._get_or_search_destination_quant(
                        line['product_id'], location_id, False, destination_quants_map,
                    )
                self._process_shortage_logic(quant, line, location_id, package_id, shortage_quant)
                


            else:
                if location_id == line['location_id'] and package_id == line['package_id']:
                    continue
                diff_qty = quant.inventory_diff_quantity
                quantity = line['quantity']
                quant_quantity = quant.quantity
                if quant_quantity > 0:
                    move_qty = max(line['quantity'] - diff_qty, 0)
                    if move_qty > 0:
                        line['quantity'] = move_qty
                        self.move(line, location_id, package_id)
                
                destination_quant = self._get_or_search_destination_quant(
                    line['product_id'], location_id, package_id, destination_quants_map,
                )
                self._process_surplus_logic(
                    quant, line, location_id, package_id, quantity, diff_qty,
                    quant_quantity, inventory_user_id, destination_quant,
                )

        return True

    def move(self, data, location_id, package_id):
        if data['quantity'] <= 0:
            return False

        try:
            move_context = {'skip_mataa_quant_sync': True}
            move = self.env['stock.move'].sudo().with_context(**move_context).create({
                'name': 'Inventory Package Move',
                'product_id': data['product_id'],
                'product_uom_qty': data['quantity'],
                'product_uom': self.env['product.product'].browse(data['product_id']).uom_id.id,
                'location_id': data['location_id'],
                'location_dest_id': location_id,
            })

            move._action_confirm()
            move._action_assign()

            if move.move_line_ids:
                for line in move.move_line_ids:
                    line.with_context(**move_context).write({
                        'qty_done': data['quantity'],
                        'package_id': data['package_id'],
                        'result_package_id': package_id,
                    })
            else:
                self.env['stock.move.line'].sudo().with_context(**move_context).create({
                    'move_id': move.id,
                    'product_id': data['product_id'],
                    'location_id': data['location_id'],
                    'location_dest_id': location_id,
                    'package_id': data['package_id'],
                    'result_package_id': package_id,
                    'qty_done': data['quantity'],
                    'product_uom_id': move.product_uom.id,
                })

            move._action_done()
            return True
        except Exception as e:
            _logger.error('Inventory move failed for product %s: %s', data['product_id'], str(e))
            raise Exception(_('Failed to move product %s. Please check the logs for more details.') % self.env['product.product'].browse(data['product_id']).display_name)
