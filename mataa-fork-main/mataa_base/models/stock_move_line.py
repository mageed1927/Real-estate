# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    @api.model_create_multi
    def create(self, vals):
        location_ids = self.env.company.mataa_in_stock_locations_ids

        sml_ids = super(StockMoveLine, self).create(vals)

        to_inhouse_sml_ids = sml_ids.filtered(
            lambda l: l.location_dest_id.id in location_ids.ids
        )

        if to_inhouse_sml_ids:
            products = to_inhouse_sml_ids.mapped("product_id").filtered(
                lambda p: not p.was_in_house
            )
            if products:
                products.write({"was_in_house": True})
        return sml_ids

    def _action_done(self):

        inhouse_location = self.env["stock.location"].search(
            [("complete_name", "=", "WH/Stock/Inhouse")], limit=1
        )
        if inhouse_location:
            relevant_move_lines = self.filtered(
                lambda ml: ml.state != "done"
                and ml.location_dest_id == inhouse_location
            )
            if relevant_move_lines:
                products_needing_rule_check = relevant_move_lines.mapped("product_id")
                existing_rules = self.env["stock.warehouse.orderpoint"].search(
                    [
                        ("product_id", "in", products_needing_rule_check.ids),
                        ("location_id", "=", inhouse_location.id),
                    ]
                )
                products_with_rules = existing_rules.mapped("product_id")
                products_needing_a_rule = (
                    products_needing_rule_check - products_with_rules
                )
                if products_needing_a_rule:
                    products_needing_a_rule.mapped(
                        "product_tmpl_id"
                    )._sync_replenishment_rules()

        super(StockMoveLine, self)._action_done()

