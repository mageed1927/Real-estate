from odoo import api, models
from odoo.exceptions import UserError


class PackageService:

    @staticmethod
    def check_existing_product(env, product_variant_barcode):
        # Check if product exist
        variant = env['product.product'].search([('barcode', '=', product_variant_barcode.strip())])
        return variant or False

    @staticmethod
    def check_existing_package(env, package_name):
        # Check if package exist
        package = env['stock.quant.package'].search([('name', '=', package_name.strip())])
        return package or False

    @staticmethod
    def find_move(env, variant, moves):
        for move in moves:
            if move.product_id == variant:
                return move
        return None

    @staticmethod
    def product_assign_with_package(env, move, variant, package, qty):
        move_line = move.move_line_ids.filtered(lambda l: not l.result_package_id or l.result_package_id.id == package.id)
        if move_line:
            move_line.write({
                'result_package_id': package.id,
                'quantity': qty
            })
        else:
            move_line_vals = {
                'move_id': move.id,
                'product_id': variant.id,
                'product_uom_id': move.product_uom.id,
                'quantity': qty,
                'location_id': move.location_id.id,
                'location_dest_id': move.location_dest_id.id,
                'result_package_id': package.id,
                'picking_id': move.picking_id.id,
                'company_id': move.company_id.id,
            }
            env['stock.move.line'].create(move_line_vals)
