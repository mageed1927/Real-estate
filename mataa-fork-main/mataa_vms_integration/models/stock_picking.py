# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def button_validate(self):
        """
        Override the button_validate method to modify the generated journal entry for in-house VMS vendors.
        Instead of creating a new journal entry, this method finds the one created by the standard
        Odoo flow and modifies the credit line to use the configured in-house payable account.
        """
        # Execute the standard validation logic first, which creates the account.move
        res = super(StockPicking, self).button_validate()

        for picking in self:
            # Check if the picking is for an incoming shipment from an in-house VMS vendor
            if not (picking.picking_type_code == 'incoming' and picking.partner_id.is_vms_vendor and picking.partner_id.vendor_type == 'in_house'):
                continue

            # Get the configured special payable account for in-house vendors
            inhouse_payable_account = picking.company_id.property_account_payable_inhouse_id
            if not inhouse_payable_account:
                _logger.warning(f"VMS In-house Payable Account not configured for company {picking.company_id.name}. "
                                f"Skipping liability modification for picking {picking.name}.")
                continue

            # Find all stock moves and their related journal entries
            stock_moves = picking.move_ids.filtered(lambda m: m.state == 'done' and m.account_move_ids)
            for move in stock_moves:
                # The account to find is the 'Stock Input Account' on the product's category
                account_to_replace = move.product_id.categ_id.property_stock_account_input_categ_id

                for account_move in move.account_move_ids:
                    if account_move.state == 'posted':
                        # Find the specific journal line to modify
                        for line in account_move.line_ids:
                            if line.account_id == account_to_replace and line.credit > 0:
                                # Use with_context to bypass validation checks on a posted entry
                                line.with_context(check_move_validity=False).write({
                                    'account_id': inhouse_payable_account.id
                                })
                                _logger.info(f"Redirected journal entry {account_move.name} for VMS in-house receipt "
                                             f"{picking.name}. Set credit account to {inhouse_payable_account.display_name}.")

        return res
