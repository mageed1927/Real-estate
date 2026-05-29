from odoo import api, fields, models, _
from odoo.tools import float_compare
from odoo.exceptions import ValidationError

from odoo.tools import float_is_zero

from odoo.exceptions import UserError
from ..services.package_service import PackageService


class StockMove(models.Model):
    _inherit = 'stock.move'

    @api.model_create_multi
    def create(self, vals):
        res = super(StockMove, self).create(vals)
        for move in res:
            if move.purchase_line_id:
                continue
            if move.picking_id.origin and move.picking_id.picking_type_id.id in [7, 1]:
                line_id = self.env['purchase.order.line'].sudo().search([
                    ('order_id.name', '=', move.picking_id.origin),
                    ('product_id', '=', move.product_id.id)
                ])
                if line_id:
                    move.purchase_line_id = line_id.id
        return res

    def _action_done(self, cancel_backorder=False):
        if not self.env.user.has_group('mataa_order_management.group_allow_stock_nagatif'):
            p = self.env["decimal.precision"].precision_get("Product Unit of Measure")
            # MRP allows scrapping draft moves
            moves = self.filtered(
                lambda move: move.state == 'draft' or float_is_zero(
                    move.product_uom_qty, precision_rounding=move.product_uom.rounding))._action_confirm(merge=False)
            moves = (self | moves).exists().filtered(lambda x: x.state not in ('done', 'cancel'))
            for move in moves:
                if move.location_id.usage in ["internal", "transit"] and move.product_id.type == "product":
                    available_qty = self.env["stock.quant"]._get_available_quantity(
                        product_id=move.product_id, location_id=move.location_id, strict=True, allow_negative=True)
                    if float_compare(available_qty, 0, precision_digits=p) == -1:
                        raise ValidationError(
                            _(
                                "You cannot validate this stock operation because the "
                                "stock level of the product '%(name)s' would "
                                "become negative "
                                "(%(q_quantity)s) on the stock location '%(complete_name)s' "
                                "and negative stock is "
                                "not allowed."
                            )
                            % {
                                "name": move.product_id.display_name,
                                "q_quantity": available_qty,
                                "complete_name": move.location_id.complete_name,
                            }
                        )
        return super(StockMove, self)._action_done(cancel_backorder)

    def _prepare_account_move_line(self, qty, cost, credit_account_id, debit_account_id, svl_id, description):
        res = super(StockMove, self)._prepare_account_move_line(qty, cost, credit_account_id, debit_account_id, svl_id, description)
        if self._context.get( 'scrap_responsible_partner_id', False):

            partner_id = self.env['res.partner'].browse(self._context['scrap_responsible_partner_id'])

            debit_side_copy = res[1][2].copy()

            debit_side_clearance = debit_side_copy.copy()
            debit_side_clearance.update({'balance': debit_side_clearance['balance']*-1})

            partner_credit_side = debit_side_copy.copy()
            partner_credit_side.update({'partner_id': partner_id.id,
                                    'account_id': partner_id.property_account_receivable_id.id})

            res.append((0, 0, debit_side_clearance))
            res.append((0, 0, partner_credit_side))
        elif self._context.get('scrap_analytic_account_id', False):
            if res:
                res[1][2].update({'analytic_distribution': { self._context['scrap_analytic_account_id']: 100}})
        return res

    def _action_confirm(self, merge=True, merge_into=False):
        res = super(StockMove, self)._action_confirm(merge, merge_into)
        for move in res:
            if move.purchase_line_id and move.picking_code == 'incoming' and move.purchase_line_id.package_name:
                package = PackageService.check_existing_package(self.env, move.purchase_line_id.package_name)
                if not package:
                    raise UserError("Package wasn't found, please check the package name!")

                # Start of the import process
                PackageService.product_assign_with_package(self.env, move, move.product_id, package, move.quantity)
        return res
