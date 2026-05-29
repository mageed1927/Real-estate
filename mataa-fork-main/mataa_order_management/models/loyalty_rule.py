from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)

class LoyaltyRule(models.Model):
    _inherit = 'loyalty.rule'

    customer_ids = fields.Many2many(
        'res.partner',
        'loyalty_rule_customer_rel',
        'rule_id',
        'partner_id',
        string='Specific Customers',
        domain=[('is_company', '=', False)],
        help="Leave empty to apply to all customers, or select specific customers"
    )

    usage_limit_per_customer = fields.Integer(
        string='Usage Limit Per Customer',
        default=0,
        help="Maximum number of times each customer can use this discount. 0 means unlimited."
    )

    customer_usage_ids = fields.One2many(
        'loyalty.rule.customer.usage',
        'rule_id',
        string='Customer Usage Tracking'
    )

    brand_ids = fields.Many2many(
        'product.brand',
        string='Brands / العلامات التجارية',
        help='Leave empty to apply to all brands.'
    )
    vendor_ids = fields.Many2many(
        'res.partner',
        string='Vendors / الموردون',
        domain="[('supplier_rank','>',0)]",
        help='Leave empty to apply to all vendors.'
    )
    website_categ_ids = fields.Many2many(
        'product.public.category',
        string='Website Categories / فئات الموقع',
        help='Leave empty to apply to all website categories.'
    )

    limit_free_shipping_by_city = fields.Boolean(
        string='Restrict free shipping by city / تقييد التوصيل المجاني حسب المدينة'
    )
    allowed_city_ids = fields.Many2many(
        'mataa.city',
        string='Allowed Cities / المدن المسموح بها',
        help='Select allowed shipping cities.'
    )

    def _order_matches_city_restriction(self, order):
        self.ensure_one()
        if not self.limit_free_shipping_by_city:
            return True
        if not self.allowed_city_ids:
            return True
        shipping_city = order.mataa_city_id
        return bool(shipping_city and shipping_city in self.allowed_city_ids)

    def _order_matches_product_filters(self, order):
        self.ensure_one()
        lines = order.order_line.filtered(lambda l: not l.is_delivery and l.product_id)
        if not lines:
            return False

        def _match_line(l):
            tmpl = l.product_id.product_tmpl_id

            ok_brand = not self.brand_ids or (
                    tmpl.product_brand_id and tmpl.product_brand_id in self.brand_ids
            )
            ok_vendor = not self.vendor_ids or (
                    tmpl.seller_ids and
                    (tmpl.seller_ids.mapped('partner_id') & self.vendor_ids)
            )

            ok_webcat = not self.website_categ_ids or (
                    tmpl.public_categ_ids and (tmpl.public_categ_ids & self.website_categ_ids)
            )

            return ok_brand or ok_vendor or ok_webcat

        return any(_match_line(l) for l in lines)


    def _check_customer_eligibility(self, partner_id):
        if not self.customer_ids:
            return True
        return partner_id in self.customer_ids.ids

    def _check_usage_limit(self, partner_id, order_id=None):
        if self.usage_limit_per_customer == 0:
            return True

        # Count all past usages across different sale orders
        domain = [
            ('rule_id', '=', self.id),
            ('partner_id', '=', partner_id),
        ]

        if order_id:
            domain.append(('order_id', '!=', order_id))

        usage_count = self.env['loyalty.rule.customer.usage'].search_count(domain)

        _logger.info(f"Usage check - Rule: {self.id}, Customer: {partner_id}, "
                     f"Current usage: {usage_count}, Limit: {self.usage_limit_per_customer}")

        return usage_count < self.usage_limit_per_customer

    def _is_valid_for_customer(self, partner_id=None, order_id=None):
        self.ensure_one()

        if not self.active:
            return False

        if not self._check_customer_eligibility(partner_id):
            _logger.info(f"Customer {partner_id} not eligible for rule {self.id}")
            return False

        if not self._check_usage_limit(partner_id, order_id):
            _logger.info(f"Customer {partner_id} exceeded usage limit for rule {self.id}")
            return False

        today = fields.Date.today()
        if getattr(self, 'validity_start', False) and self.validity_start > today:
            return False
        if getattr(self, 'validity_end', False) and self.validity_end < today:
            return False

        if not order_id:
            return True

        order = order_id if hasattr(order_id, 'id') else self.env['sale.order'].browse(order_id)

        if any([self.brand_ids, self.vendor_ids, self.website_categ_ids]):
            if not self._order_matches_product_filters(order):
                return False

        if not self._order_matches_city_restriction(order):
            return False

        return True

    def _create_usage_record(self, partner_id, order_id):
        if self.usage_limit_per_customer > 0:
            # Check if record already exists to avoid duplicates
            existing = self.env['loyalty.rule.customer.usage'].search([
                ('rule_id', '=', self.id),
                ('partner_id', '=', partner_id),
                ('order_id', '=', order_id)
            ])

            if not existing:
                usage_record = self.env['loyalty.rule.customer.usage'].create({
                    'rule_id': self.id,
                    'partner_id': partner_id,
                    'order_id': order_id,
                    'usage_date': fields.Datetime.now()
                })
                _logger.info(f"Created usage record {usage_record.id} for rule {self.id}, "
                             f"customer {partner_id}, order {order_id}")
                return usage_record
        return False


class LoyaltyRuleCustomerUsage(models.Model):
    _name = 'loyalty.rule.customer.usage'
    _description = 'Track loyalty rule usage per customer'
    _rec_name = 'partner_id'

    rule_id = fields.Many2one('loyalty.rule', string='Loyalty Rule', required=True, ondelete='cascade')
    partner_id = fields.Many2one('res.partner', string='Customer', required=True)
    usage_date = fields.Datetime(string='Usage Date', default=fields.Datetime.now)
    order_id = fields.Many2one('sale.order', string='Related Order')

    _sql_constraints = [
        ('unique_usage', 'unique(rule_id, partner_id, order_id)',
         'Usage record must be unique per rule, customer, and order')
    ]