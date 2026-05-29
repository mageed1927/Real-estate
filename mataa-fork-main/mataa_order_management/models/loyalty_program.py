from odoo import models, fields, api

class LoyaltyProgram(models.Model):
    _inherit = 'loyalty.program'

    def _check_rule_validity(self, rule, partner_id,order_id=None):
        is_valid = super()._check_rule_validity(rule, partner_id)

        if not is_valid:
            return False

        # Add our custom customer checks
        return rule._is_valid_for_customer(partner_id=partner_id, order_id=order_id)

    def _get_valid_rules(self, partner_id=None):
        valid_rules = super()._get_valid_rules(partner_id)

        if not partner_id:
            return valid_rules

        # Filter rules based on customer restrictions
        customer_valid_rules = valid_rules.filtered(
            lambda rule: rule._is_valid_for_customer(partner_id)
        )

        return customer_valid_rules