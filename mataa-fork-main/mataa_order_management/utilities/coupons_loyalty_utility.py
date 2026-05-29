from collections import defaultdict

from datetime import date
from odoo.osv import expression
from odoo import _

from odoo.tools import float_round, float_is_zero

from odoo.exceptions import UserError


class CouponsLoyaltyUtility:

    @staticmethod
    def _try_apply_code(env, customer, coupon_code, order_lines, coupons_points):
        base_domain = CouponsLoyaltyUtility._get_trigger_domain()
        domain = expression.AND([base_domain, [('mode', '=', 'with_code'), ('code', '=', coupon_code)]])
        rule = env['loyalty.rule'].sudo().search(domain)
        program = rule.program_id
        coupon = False
        # coupons_points = dict()
        # No trigger was found from the code, try to find a coupon
        if not program:
            coupon = env['loyalty.card'].sudo().search([('code', '=', coupon_code)])
            if not coupon or\
                not coupon.program_id.active or\
                not coupon.program_id.reward_ids or\
                not coupon.program_id.filtered_domain(CouponsLoyaltyUtility._get_program_domain()):
                return {'error': _('This code is invalid (%s).', coupon_code), 'not_found': True}
            elif coupon.expiration_date and coupon.expiration_date < date.today():
                return {'error': _('This coupon is expired.')}
            elif coupon.points < min(coupon.program_id.reward_ids.mapped('required_points')):
                return {'error': _('This coupon has already been used.')}
            program = coupon.program_id

        if not program or not program.active:
            return {'error': _('This code is invalid (%s).', coupon_code), 'not_found': True}
        elif (program.limit_usage and program.total_order_count >= program.max_usage):
            return {'error': _('This code is expired (%s).', coupon_code)}
        if program.applies_on != 'future' or not coupon:
            apply_result = CouponsLoyaltyUtility._try_apply_program(env, customer, program, coupons_points, coupon, order_lines)
            if 'error' in apply_result and (not program.is_nominative or (program.is_nominative and not coupon)):
                return apply_result
            coupon = apply_result.get('coupon', env['loyalty.card'])
        return CouponsLoyaltyUtility._get_claimable_rewards(env, coupons_points, order_lines, forced_coupons=coupon)

    @staticmethod
    def _get_trigger_domain():
        today = date.today()
        return [('active', '=', True), ('program_id.sale_ok', '=', True),
                '|', ('program_id.pricelist_ids', '=', False),
                '|', ('program_id.date_from', '=', False), ('program_id.date_from', '<=', today),
                '|', ('program_id.date_to', '=', False), ('program_id.date_to', '>=', today)]

    @staticmethod
    def _get_program_domain():
        today = date.today()
        return [('active', '=', True), ('sale_ok', '=', True),
                '|', ('date_from', '=', False), ('date_from', '<=', today),
                '|', ('date_to', '=', False), ('date_to', '>=', today)]

    @staticmethod
    def _try_apply_program(env, customer, program, coupons_points, coupon=None, order_lines=[]):
        # Basic checks
        if not program.filtered_domain(CouponsLoyaltyUtility._get_program_domain()):
            return {'error': _('The program is not available for this order.')}

        status = CouponsLoyaltyUtility._program_check_compute_points(env, program, order_lines)[program]
        if 'error' in status:
            return status
        return CouponsLoyaltyUtility.__try_apply_program(env, customer, program, coupon, status, coupons_points)

    @staticmethod
    def __try_apply_program(env, customer, program, coupon, status, coupons_points):
        all_points = status['points']
        points = all_points[0]
        coupons = coupon or env['loyalty.card']

        if coupon:
            if program.is_nominative:
                CouponsLoyaltyUtility._add_points_for_coupon(coupons_points, {coupon: points})
                print('98******', coupons_points)
        elif not coupon:
            # If the program only applies on the current order it does not make sense to fetch already existing coupons
            if program.is_nominative:
                coupon = env['loyalty.card'].sudo().search(
                    [('partner_id', '=', customer.id), ('program_id', '=', program.id)], limit=1)
                # Do not apply 'nominative' programs if no point is given and no coupon exists
                if not points and not coupon:
                    return {'error': _('No card found for this loyalty program and no points will be given with this order.')}
                elif coupon:
                    CouponsLoyaltyUtility._add_points_for_coupon(coupons_points, {coupon: points})
                    print('99**********', coupons_points)
                coupons = coupon
            # if not coupon:
            #     all_points = [p for p in all_points if p]
            #     partner = False
            #     # Loyalty programs and ewallets are nominative
            #     if program.is_nominative:
            #         partner = customer.id
            #     coupons = env['loyalty.card'].sudo().with_context(loyalty_no_mail=True, tracking_disable=True).create([{
            #         'program_id': program.id,
            #         'partner_id': partner,
            #         'points': 0,
            #         'order_id': self.id,
            #     } for _ in all_points])
            #     self._add_points_for_coupon({coupon: x for coupon, x in zip(coupons, all_points)})
        print('12*******', coupon, coupons_points)
        return {'coupon': coupons}

    @staticmethod
    def _get_claimable_rewards(env, coupons_points, order_lines, forced_coupons=None, coupon_code=None):
        all_coupons = forced_coupons or env['loyalty.card'].sudo().search([('code', '=', coupon_code)])
        has_payment_reward = False  # any(line.reward_id.program_id.is_payment_program for line in self.order_line)
        amount_total = CouponsLoyaltyUtility.get_amount_total(order_lines)
        total_is_zero = float_is_zero(amount_total, precision_digits=2)
        result = defaultdict(lambda: env['loyalty.reward'])
        active_products_domain = env['loyalty.reward'].sudo()._get_active_products_domain()
        for coupon in all_coupons:
            points = CouponsLoyaltyUtility._get_real_points_for_coupon(coupons_points, coupon)
            for reward in coupon.program_id.reward_ids:
                is_discount = reward.reward_type == 'discount'
                is_payment_program = reward.program_id.is_payment_program
                if is_discount and total_is_zero and (not has_payment_reward or is_payment_program):
                    continue
                # Skip discount that has already been applied if not part of a payment program
                if reward.reward_type == 'product' and not reward.filtered_domain(
                    active_products_domain
                ):
                    continue
                if points >= reward.required_points:
                    result[coupon] |= reward
        return result

    @staticmethod
    def _program_check_compute_points(env, programs, order_lines):

        # Prepare quantities
        order_lines = order_lines
        product_ids = [line['product_id'] for line in order_lines]
        products = env['product.product'].sudo().browse(product_ids)
        products_qties = dict.fromkeys(products, 0)
        for line in order_lines:
            product_id = env['product.product'].sudo().browse(line['product_id'])
            products_qties[product_id] += line['quantity']
        # Contains the products that can be applied per rule
        products_per_rule = programs._get_valid_products(products)

        # Prepare amounts
        so_products_per_rule = programs._get_valid_products(products)
        lines_per_rule = defaultdict(list)
        # Skip lines that have no effect on the minimum amount to reach.
        for line in order_lines:
            product_id = env['product.product'].sudo().browse(line['product_id'])
            for program in programs:
                for rule in program.rule_ids:
                    if product_id in so_products_per_rule.get(rule, []):
                        lines_per_rule[rule] |= line

        result = {}
        for program in programs:
            # Used for error messages
            # By default False, but True if no rules and applies_on current -> misconfigured coupons program
            code_matched = not bool(program.rule_ids) and program.applies_on == 'current' # Stays false if all triggers have code and none have been activated
            minimum_amount_matched = code_matched
            product_qty_matched = code_matched
            points = 0
            # Some rules may split their points per unit / money spent
            #  (i.e. gift cards 2x50$ must result in two 50$ codes)
            rule_points = []
            program_result = result.setdefault(program, dict())
            for rule in program.rule_ids:
                # prevent bottomless ewallet spending
                if program.program_type == 'ewallet' and not program.trigger_product_ids:
                    break
                # if rule.mode == 'with_code' and rule not in self.code_enabled_rule_ids:
                #     continue
                code_matched = True
                rule_amount = rule._compute_amount(env.sudo().company.currency_id)
                list_untaxed_amount = CouponsLoyaltyUtility.get_amounts_untaxed(lines_per_rule[rule])
                untaxed_amount = sum(list_untaxed_amount)
                tax_amount = 0
                if rule_amount > (rule.minimum_amount_tax_mode == 'incl' and (untaxed_amount + tax_amount) or untaxed_amount):
                    continue
                minimum_amount_matched = True
                if not products_per_rule.get(rule):
                    continue
                rule_products = products_per_rule[rule]
                ordered_rule_products_qty = sum(products_qties[product] for product in rule_products)
                if ordered_rule_products_qty < rule.minimum_qty or not rule_products:
                    continue
                product_qty_matched = True
                if not rule.reward_point_amount:
                    continue
                # Count all points separately if the order is for the future and the split option is enabled
                if program.applies_on == 'future' and rule.reward_point_split and rule.reward_point_mode != 'order':
                    if rule.reward_point_mode == 'unit':
                        rule_points.extend(rule.reward_point_amount for _ in range(int(ordered_rule_products_qty)))
                    elif rule.reward_point_mode == 'money':
                        for line in order_lines:
                            product_id = env['product.product'].sudo().browse(line['product_id'])
                            if product_id not in rule_products or line['quantity'] <= 0:
                                continue
                            points_per_unit = float_round(
                                (rule.reward_point_amount * line['unit_price']),
                                precision_digits=2, rounding_method='DOWN')
                            if not points_per_unit:
                                continue
                            rule_points.extend([points_per_unit] * int(line['quantity']))
                else:
                    # All checks have been passed we can now compute the points to give
                    if rule.reward_point_mode == 'order':
                        points += rule.reward_point_amount
                    elif rule.reward_point_mode == 'money':
                        # Compute amount paid for rule
                        # NOTE: this accounts for discounts -> 1 point per $ * (100$ - 30%) will
                        # result in 70 points
                        amount_paid = 0.0
                        rule_products = so_products_per_rule.get(rule, [])
                        for line in order_lines:
                            # if line.reward_id.program_id.program_type in [
                            #     'ewallet', 'gift_card', program.program_type
                            # ]:
                            #     continue
                            product_id = env['product.product'].sudo().browse(line['product_id'])
                            price_total = line['quantity'] * line['unit_price']
                            amount_paid += price_total if product_id in rule_products else 0.0

                        points += float_round(rule.reward_point_amount * amount_paid, precision_digits=2, rounding_method='DOWN')
                    elif rule.reward_point_mode == 'unit':
                        points += rule.reward_point_amount * ordered_rule_products_qty
            # NOTE: for programs that are nominative we always allow the program to be 'applied' on the order
            #  with 0 points so that `_get_claimable_rewards` returns the rewards associated with those programs
            if not program.is_nominative:
                if not code_matched:
                    program_result['error'] = _("This program requires a code to be applied.")
                elif not minimum_amount_matched:
                    program_result['error'] = _(
                        'A minimum of %(amount)s %(currency)s should be purchased to get the reward',
                        amount=min(program.rule_ids.mapped('minimum_amount')),
                        currency=program.currency_id.name,
                    )
                elif not product_qty_matched:
                    program_result['error'] = _("You don't have the required product quantities on your sales order.")
            if 'error' not in program_result:
                points_result = [points] + rule_points
                program_result['points'] = points_result
        return result

    @staticmethod
    def get_amounts_untaxed(lines_per_rule):
        return [(line_per_rule['quantity'] * line_per_rule['unit_price']) for line_per_rule in lines_per_rule]

    @staticmethod
    def get_amount_total(order_lines):
        amount_total = 0
        for line in order_lines:
            amount_total += (line['quantity'] * line['unit_price'])
        return amount_total

    @staticmethod
    def _add_points_for_coupon(coupons_points, coupon_points):
        for coupon, points in coupons_points:
            if coupon in coupon_points:
                coupons_points['points'] = coupon_points.pop(coupon)
        if coupon_points:
            for coupon, points in coupon_points.items():
                coupons_points.update({
                    'coupon_id': coupon.id,
                    'points': points,

                })

    @staticmethod
    def _get_real_points_for_coupon(coupons_points, coupon):
        points = coupon.points
        if coupon.program_id.applies_on != 'future':
            # Points that will be given by the order upon confirming the order
            for coupon, points in coupons_points:
                if coupon == coupon:
                    points += points
        points = coupon.currency_id.round(points)
        return points

    @staticmethod
    def _apply_program_reward(env, reward, coupon, coupons_points, order_lines, **kwargs):
        if CouponsLoyaltyUtility._get_real_points_for_coupon(coupons_points, coupon) < reward.required_points:
            return {'error': _('The coupon does not have enough points for the selected reward.')}
        reward_vals = CouponsLoyaltyUtility._get_reward_line_values(env, reward, coupon, coupons_points, order_lines)
        CouponsLoyaltyUtility._write_vals_from_reward_vals(reward_vals, order_lines)
        return {}

    @staticmethod
    def _get_reward_line_values(env, reward, coupon, coupons_points, order_lines):
        if reward.reward_type == 'discount':
            return CouponsLoyaltyUtility._get_reward_values_discount(env, reward, coupon, coupons_points, order_lines)
        elif reward.reward_type == 'product':
            return CouponsLoyaltyUtility._get_reward_values_product(reward, coupon, coupons_points)

    @staticmethod
    def _get_reward_values_product(reward, coupon, coupons_points, product=None):
        assert reward.reward_type == 'product'

        reward_products = reward.reward_product_ids
        product = product or reward_products[:1]
        if not product or product not in reward_products:
            raise UserError(_('Invalid product to claim.'))
        points = CouponsLoyaltyUtility._get_real_points_for_coupon(coupons_points, coupon)
        claimable_count = float_round(points / reward.required_points, precision_rounding=1, rounding_method='DOWN') if not reward.clear_wallet else 1
        cost = points if reward.clear_wallet else claimable_count * reward.required_points
        return [{
            'name': _("Free Product - %(product)s", product=product.with_context(display_default_code=False).display_name),
            'product_id': product.id,
            'discount': 100,
            'quantity': reward.reward_product_qty * claimable_count,
            'unit_price': cost,
        }]

    @staticmethod
    def _get_reward_values_discount(env, reward, coupon, coupons_points, order_lines):
        assert reward.reward_type == 'discount'

        # Figure out which lines are concerned by the discount
        discountable = 0
        discountable_per_tax = defaultdict(int)
        reward_applies_on = reward.discount_applicability
        if reward_applies_on == 'order':
            discountable, discountable_per_tax = CouponsLoyaltyUtility._discountable_order(env, reward, order_lines)
        elif reward_applies_on == 'specific':
            discountable, discountable_per_tax = CouponsLoyaltyUtility._discountable_specific(reward, order_lines)
        elif reward_applies_on == 'cheapest':
            discountable, discountable_per_tax = CouponsLoyaltyUtility._discountable_cheapest(env, reward, order_lines)
        if not discountable:
            # if not reward.program_id.is_payment_program and any(line.reward_id.program_id.is_payment_program for line in self.order_line):
            #     return [{
            #         'name': _("TEMPORARY DISCOUNT LINE"),
            #         'product_id': reward.discount_line_product_id.id,
            #         'price_unit': 0,
            #         'product_uom_qty': 0,
            #         'product_uom': reward.discount_line_product_id.uom_id.id,
            #         'reward_id': reward.id,
            #         'coupon_id': coupon.id,
            #         'points_cost': 0,
            #         'reward_identifier_code': _generate_random_reward_code(),
            #         'sequence': sequence,
            #         'tax_id': [(Command.CLEAR, 0, 0)]
            #     }]
            raise UserError(_('There is nothing to discount'))
        max_discount = reward.discount_max_amount or float('inf')
        # discount should never surpass the order's current total amount
        amount_total = CouponsLoyaltyUtility.get_amount_total(order_lines)
        max_discount = min(amount_total, max_discount)
        if reward.discount_mode == 'per_point':
            points = CouponsLoyaltyUtility._get_real_points_for_coupon(coupons_points, coupon)
            if not reward.program_id.is_payment_program:
                # Rewards cannot be partially offered to customers
                points = points // reward.required_points * reward.required_points
            max_discount = min(max_discount, reward.discount * points)
        elif reward.discount_mode == 'per_order':
            max_discount = min(max_discount, reward.discount)
        elif reward.discount_mode == 'percent':
            max_discount = min(max_discount, discountable * (reward.discount / 100))
        # Discount per taxes
        point_cost = reward.required_points if not reward.clear_wallet else CouponsLoyaltyUtility._get_real_points_for_coupon(coupons_points, coupon)
        if reward.discount_mode == 'per_point' and not reward.clear_wallet:
            # Calculate the actual point cost if the cost is per point
            converted_discount = min(max_discount, discountable)
            point_cost = converted_discount / reward.discount
        # Gift cards and eWallets are considered gift cards and should not have any taxes
        if reward.program_id.is_payment_program:
            reward_product = reward.discount_line_product_id
            reward_line_values = {
                # 'name': reward.description,
                'product_id': reward_product.id,
                'unit_price': -min(max_discount, discountable),
                'product_uom_qty': 1.0,
            }
            return [reward_line_values]
        discount_factor = min(1, (max_discount / discountable)) if discountable else 1
        reward_dict = {}
        for tax, price in discountable_per_tax.items():
            if not price:
                continue
            reward_dict[tax] = {
                'reward_name': reward.program_id.name,
                'product_id': reward.discount_line_product_id.id,
                'unit_price': -(price * discount_factor),
                'quantity': 1.0,
            }
        return list(reward_dict.values())

    @staticmethod
    def _discountable_order(env, reward, order_lines):
        assert reward.discount_applicability == 'order'
        discountable = CouponsLoyaltyUtility.get_amount_total(order_lines)
        discountable_per_tax = defaultdict(int)
        # lines = self.order_line if reward.program_id.is_payment_program else (self.order_line - self._get_no_effect_on_threshold_lines())
        for line in order_lines:
            # Ignore lines from this reward
            if not line.get('quantity', 0) or not line.get('unit_price', 0):
                continue

            line_price = line['unit_price'] * line['quantity']  #  * (1 - (line.discount or 0.0) / 100)
            discountable_per_tax[env['account.tax']] += line_price
        return discountable, discountable_per_tax

    @staticmethod
    def _discountable_specific(env, reward, order_lines):
        assert reward.discount_applicability == 'specific'

        lines_to_discount = []
        # order_lines = self.order_line - self._get_no_effect_on_threshold_lines()
        remaining_amount_per_line = defaultdict(int)
        for line in order_lines:
            if not line.get('quantity', 0) or not line.get('price_total', 0):
                continue
            remaining_amount_per_line[line] = line['quantity'] * line['unit_price']
            # domain = reward._get_discount_product_domain()
            lines_to_discount |= line

        discountable = 0
        discountable_per_tax = defaultdict(int)
        for line in lines_to_discount:
            discountable += remaining_amount_per_line[line]
            line_discountable = line['unit_price'] * line['quantity']  # * (1 - (line.discount or 0.0) / 100.0)
            # line_discountable is the same as in a 'order' discount
            #  but first multiplied by a factor for the taxes to apply
            #  and then multiplied by another factor coming from the discountable
            taxes = env['account.tax']
            discountable_per_tax[taxes] += line_discountable *\
                (remaining_amount_per_line[line] / line.price_total)
        return discountable, discountable_per_tax

    @staticmethod
    def _discountable_cheapest(env, reward, order_lines):
        assert reward.discount_applicability == 'cheapest'

        cheapest_line = CouponsLoyaltyUtility._cheapest_line(order_lines)
        if not cheapest_line:
            return False, False
        discountable = cheapest_line['quantity'] * cheapest_line['unit_price']
        discountable_per_taxes = cheapest_line['unit_price']  # * (1 - (cheapest_line.discount or 0) / 100)
        taxes = env['account.tax']  # cheapest_line.tax_id.filtered(lambda t: t.amount_type != 'fixed')

        return discountable, {taxes: discountable_per_taxes}

    @staticmethod
    def _cheapest_line(order_lines):
        cheapest_line = False
        for line in order_lines:
            if not line.get('quantity', 0) or not line.get('unit_price'):
                continue
            if not cheapest_line or cheapest_line['unit_price'] > line['unit_price']:
                cheapest_line = line
        return cheapest_line

    @staticmethod
    def _write_vals_from_reward_vals(reward_vals, order_lines):
        order_lines += reward_vals
