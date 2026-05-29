# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    def _default_report_bank_transfer_team(self):
        return self.env['helpdesk.team'].search([('name', '=', 'Finance')], limit=1)

    note_tag_rule_ids = fields.One2many(
        related='company_id.note_tag_rule_ids',
        readonly=False,
        string="Note Tag Rules"
    )

    payment_due_notification_user_ids = fields.Many2many(
        related='company_id.payment_due_notification_user_ids',
        readonly=False
    )

    refund_support_team_id = fields.Many2one(
        'helpdesk.team',
        related='company_id.refund_support_team_id',
        string='Refund Support Team',
        readonly=False
    )
    refund_support_stage_id = fields.Many2one(
        'helpdesk.stage',
        related='company_id.refund_support_stage_id',
        string='Default Refund Stage',
        readonly=False,
        domain="[('team_id', '=', refund_support_team_id)]"
    )

    mataa_vendor = fields.Many2one('res.partner',
                                     string='Default Vendor',
                                     config_parameter='mataa_order_management.mataa_vendor',
                                     default=False)

    blanket_order_qty_limit = fields.Integer(
                                     string="Default Blanket Order Quantity Limit",
                                     config_parameter='mataa_order_management.blanket_order_qty_limit',
                                     default=50
    )

    wallet_api_base_url = fields.Char(string="Wallet URL", config_parameter="mataa_order_management.wallet_api_base_url")

    dtrack_api_base_url = fields.Char(string="Dtrack API Base Url", config_parameter="mataa_order_management.dtrack_api_base_url")
    dtrack_api_key = fields.Char(string="API Key", config_parameter="mataa_order_management.dtrack_api_key")

    vendor_notification_webhook = fields.Char(string="Vendor Notification Webhook", config_parameter="mataa_order_management.vendor_notification_webhook")

    dtrack_customer_key = fields.Char(string="Customer Key", config_parameter="mataa_order_management.dtrack_customer_key")
    dtrack_customer_secret = fields.Char(string="Customer Secret", config_parameter="mataa_order_management.dtrack_customer_secret")

    wallet_reservation_journal_id = fields.Many2one('account.journal',
                                                    related='company_id.wallet_reservation_journal_id',
                                                    domain=[('type', '=', 'general')],
                                                    readonly=False, help='Select the journal for wallet reservations.')

    wallet_reservation_account_id = fields.Many2one('account.account',
                                                    related='company_id.wallet_reservation_account_id',
                                                    domain=[('account_type', '=', 'asset_receivable')],
                                                    readonly=False, help='Select the account for wallet reservations.')

    vendor_support_team_id = fields.Many2one('helpdesk.team', related='company_id.vendor_support_team_id', readonly=False,
                                             help='Select the support team for vendors related tickets.')

    customer_support_team_id = fields.Many2one('helpdesk.team', related='company_id.customer_support_team_id', readonly=False,
                                             help='Select the support team for customers related tickets.')

    order_closing_support_team_id = fields.Many2one('helpdesk.team', related='company_id.order_closing_support_team_id', readonly=False,
                                             help='Select the support team for order closing tickets.')

    activity_default_res_id = fields.Many2one(
        'res.users',
        related='company_id.activity_default_res_id',
        readonly=False,
        string="user responsible for closing orders",
        help="user responsible for closing orders"
    )

    review_price_default_res_id = fields.Many2one(
        comodel_name='res.users',
        string="Default user for reviewing invoice prices",
        config_parameter='mataa_order_management.default_user_review_order_price_id',
        help="This user will be assigned a planned activity if invoice price is below cost.",
        default_model='res.config.settings'
    )

    auto_confirm_in_house_orders = fields.Boolean(related='company_id.auto_confirm_in_house_orders', readonly=False,
                                                  help='Check this to auto confirm in house orders.')

    auto_confirm_enabled = fields.Boolean(
        string="Enable Auto Confirmation",
        config_parameter="mataa_order_management.auto_confirm_enabled",
        help="If disabled, orders will not be auto-confirmed."
    )

    auto_confirm_enable_customer_note = fields.Boolean(
        string="Exclude Orders with Customer Notes",
        config_parameter="mataa_order_management.auto_confirm_enable_customer_note",
        help="If enabled, orders with customer notes will not be auto-confirmed."
    )

    auto_confirm_amount_limit = fields.Float(
        string="Auto Confirm Amount Limit",
        config_parameter="mataa_order_management.auto_confirm_amount_limit",
        help="Orders equal or above this amount will not be auto-confirmed."
    )

    auto_confirm_order_count_limit = fields.Integer(
        string="Auto Confirm Customer Orders Limit",
        config_parameter="mataa_order_management.auto_confirm_order_count_limit",
        help="If customer has this number of orders or more, the order will not be auto-confirmed."
    )

    auto_confirm_check_active_order = fields.Boolean(
        string="Exclude Customers with Active Orders",
        config_parameter="mataa_order_management.auto_confirm_check_active_order",
        help="If enabled, customers with active sale orders will be excluded from auto-confirmation."
    )

    auto_confirm_check_refunds = fields.Boolean(
        string="Exclude Customers with Refund Orders",
        config_parameter="mataa_order_management.auto_confirm_check_refunds",
        help="If enabled, customers who have refund orders will be excluded from auto-confirmation."
    )

    auto_confirm_excluded_city_ids = fields.Many2many(
        'mataa.city',
        string="Excluded Cities from Auto Confirmation",
        help="Orders from these cities will not be auto-confirmed."
    )

    auto_confirm_excluded_city_ids_text = fields.Char(
        string="Excluded Cities (Internal Storage)",
        config_parameter="mataa_order_management.auto_confirm_excluded_city_ids",
        invisible=True
    )

    validate_api_stock = fields.Boolean(
        string="Validate Stock When Creating SO from API",
        config_parameter="mataa_order_management.validate_api_stock",
        help="If enabled, the API will reject creating a sale order when a product has zero free quantity."
    )

    @api.model
    def get_values(self):
        res = super().get_values()
        IrConfig = self.env['ir.config_parameter'].sudo()
        city_ids_str = IrConfig.get_param('mataa_order_management.auto_confirm_excluded_city_ids', '[]')

        try:
            city_ids = eval(city_ids_str) if city_ids_str else []
        except Exception:
            city_ids = []

        res.update({
            'auto_confirm_excluded_city_ids': [(6, 0, city_ids)],
        })
        return res

    def set_values(self):
        super().set_values()
        IrConfig = self.env['ir.config_parameter'].sudo()
        city_ids_str = str(self.auto_confirm_excluded_city_ids.ids or [])
        IrConfig.set_param('mataa_order_management.auto_confirm_excluded_city_ids', city_ids_str)

    prices_control = fields.Boolean("Prices control", config_parameter="mataa_order_management.prices_control")

    shipping_deviation_threshold = fields.Integer(
        related='company_id.shipping_deviation_threshold',
        readonly=False
    )

    # For refunds and returns
    mataa_return_location_id = fields.Many2one('stock.location', related='company_id.mataa_return_location_id', readonly=False)
    mataa_return_picking_type_id = fields.Many2one('stock.picking.type', related='company_id.mataa_return_picking_type_id', readonly=False)
    mataa_return_inhouse_location_id = fields.Many2one('stock.location', related='company_id.mataa_return_inhouse_location_id', readonly=False)

    mataa_refund_route_id = fields.Many2one('stock.route', related='company_id.mataa_refund_route_id', readonly=False)

    external_vendor_api_url = fields.Char(
    string = "External Vendor API URL",
    config_parameter = "mataa_order_management.external_vendor_api_url"
    )

    external_vendor_api_username = fields.Char(
        string="External Vendor API Username",
        config_parameter="mataa_order_management.external_vendor_api_username"
    )

    external_vendor_api_password = fields.Char(
        string="External Vendor API Password",
        config_parameter="mataa_order_management.external_vendor_api_password"
    )



    refund_orders_journal_id = fields.Many2one('account.journal',
                                               related='company_id.refund_orders_journal_id',
                                               domain=[('type', 'in', ['cash', 'bank'])],
                                               readonly=False, help='Select the journal for refund orders payments.')

    compensation_window_days = fields.Integer(
        string="Compensation Window (Days)",
        config_parameter='mataa_order_management.compensation_window_days',
        default=30,
        help='Number of days after delivery to allow compensation'
    )
    
    compensation_allowable_percentage = fields.Float(
        string="Compensation Allowable Percentage (%)",
        config_parameter='mataa_order_management.compensation_allowable_percentage',
        help='Maximum percentage of order total that can be compensated (for regular users)'
    )
    
    compensation_account_id = fields.Many2one(
        'account.account',
        string='Client Compensation Account',
        config_parameter='mataa_order_management.compensation_account_id',
        help='Account to debit for client compensation'
    )
    
    compensation_journal_id = fields.Many2one(
        'account.journal',
        string='Compensation Journal',
        config_parameter='mataa_order_management.compensation_journal_id',
        domain=[('type', '=', 'general')],
        help='Journal to use for compensation entries'
    )

    external_sale_url = fields.Char(
        string='External Sale Order URL',
        config_parameter='mataa_order_management.external_sale_url',
        default='http://88.198.77.169/',
        help='URL for external sale order creation system'
    )

    batch_carrier_id = fields.Many2one(
        'delivery.carrier',
        string='Default Carrier for Batching',
        config_parameter='mataa_order_management.batch_carrier_id'
    )

    discount_reason_ids = fields.Many2many(
        'price.adjustment.reason',
        related='company_id.discount_reason_ids',
        string="Discount Reasons",
        readonly=False)

    api_key = fields.Char(
        string="Public API Key",
        config_parameter='mataa_order_management.api_key',
        help="Key required in the X-API-KEY header for public API calls.",
    )

    external_api_token = fields.Char(
        string="External API Token",
        help="Token sent on every request to the external Order Management API.",
        config_parameter='mataa_order_management.external_api_token',
        password=True,
    )

    report_bank_transfer_team_name = fields.Many2one(
        'helpdesk.team',
        string="Bank Transfer Team",
        config_parameter='mataa_order_management.report_bank_transfer_team_name',
        default=_default_report_bank_transfer_team,
        help="Helpdesk team used by /api/report_bank_transfer endpoint."
    )

    report_bank_transfer_stage_name = fields.Char(
        string="Bank Transfer Stage Name",
        config_parameter='mataa_order_management.report_bank_transfer_stage_name',
        default='تحويلات مصرفية',
        help="Helpdesk stage name used by /api/report_bank_transfer endpoint."
    )

    report_bank_transfer_tag_name = fields.Char(
        string="Bank Transfer Tag Name",
        config_parameter='mataa_order_management.report_bank_transfer_tag_name',
        default='تحويلات مصرفية',
        help="Helpdesk tag name used by /api/report_bank_transfer endpoint."
    )

    report_bank_transfer_ticket_name = fields.Char(
        string="Bank Transfer Ticket Title",
        config_parameter='mataa_order_management.report_bank_transfer_ticket_name',
        default='مراجعة تحويل مصرفي',
        help="Helpdesk ticket title used by /api/report_bank_transfer endpoint."
    )

    report_order_issue_team_name = fields.Many2one(
        'helpdesk.team',
        string="Order Issue Team",
        config_parameter='mataa_order_management.report_order_issue_team_name',
        help="Helpdesk team used by /api/report_order_issue endpoint."
    )

    report_order_issue_stage_name = fields.Char(
        string="Order Issue Stage Name",
        config_parameter='mataa_order_management.report_order_issue_stage_name',
        help="Helpdesk stage name used by /api/report_order_issue endpoint."
    )

    card_on_delivery_trigger_code = fields.Selection(
        related='company_id.card_on_delivery_trigger_code',
        readonly=False,
        string="Trigger Code (Source)"
    )

    card_on_delivery_journal_id = fields.Many2one(
        related='company_id.card_on_delivery_journal_id',
        readonly=False,
        string="Destination Journal"
    )

    mataa_discount_account_id = fields.Many2one(
        'account.account',
        related='company_id.mataa_discount_account_id',
        readonly=False,
        string="Mataa Discount Account",
        domain="[('deprecated', '=', False)]",
        help="The account where the marketing discount difference will be recorded."
    )

    mataa_discount_label = fields.Char(
        related='company_id.mataa_discount_label',
        readonly=False,
        string="Discount Label",
        config_parameter='mataa_order_management.mataa_discount_label'
    )

    mataa_shipping_discount_account_id = fields.Many2one(
        'account.account',
        related='company_id.mataa_shipping_discount_account_id',
        readonly=False,
        string="Shipping Discount Account"
    )

    mataa_shipping_discount_label = fields.Char(
        related='company_id.mataa_shipping_discount_label',
        readonly=False,
        string="Shipping Discount Label",
        config_parameter='mataa_order_management.mataa_shipping_discount_label'
    )


class Company(models.Model):
    _inherit = "res.company"

    note_tag_rule_ids = fields.One2many('mataa.note.tag.rule', 'company_id', string='Note Tag Rules')

    payment_due_notification_user_ids = fields.Many2many(
        'res.users',
        'company_payment_notification_rel',
        'company_id',
        'user_id',
        string="Users for Payment Due Notifications"
    )

    refund_support_team_id = fields.Many2one('helpdesk.team', string='Refund Support Team',
                                             help='Default support team for refund tickets.')
    refund_support_stage_id = fields.Many2one('helpdesk.stage', string='Default Refund Stage',
                                              help='Default stage for new refund tickets.')

    wallet_reservation_journal_id = fields.Many2one('account.journal', domain=[('type', '=', 'general')],
                                                    help='Select the journal for wallet reservations.')

    wallet_reservation_account_id = fields.Many2one('account.account', domain=[('account_type', '=', 'asset_receivable')],
                                                    help='Select the account for wallet reservations.')

    vendor_support_team_id = fields.Many2one('helpdesk.team', help='Select the support team for vendors related tickets.')

    customer_support_team_id = fields.Many2one('helpdesk.team', help='Select the support team for customers related tickets.')

    order_closing_support_team_id = fields.Many2one('helpdesk.team', help='Select the support team for order closing tickets.')

    activity_default_res_id = fields.Many2one(
        'res.users',
        string="user responsible for closing orders",
        help="user responsible for closing orders"
    )

    auto_confirm_in_house_orders = fields.Boolean(help='Check this to auto confirm in house orders.')

    shipping_deviation_threshold = fields.Integer(
        string="Shipping Deviation Threshold Percent", default=0
    )


    # For refunds and returns
    mataa_return_location_id = fields.Many2one('stock.location', string="Return Location")
    mataa_return_picking_type_id = fields.Many2one('stock.picking.type', string="Return Operation Type")
    mataa_return_inhouse_location_id = fields.Many2one('stock.location', string="Default Return Inhouse Location")
    mataa_refund_route_id = fields.Many2one('stock.route', string="Refund Route")


    refund_orders_journal_id = fields.Many2one('account.journal',
                                               domain=[('type', 'in', ['cash', 'bank'])],
                                               help='Select the journal for refund orders payments.')

    discount_reason_ids = fields.Many2many(
        'price.adjustment.reason',
        string="Discount Reasons",
    )

    def _get_journal_code_selection(self):
        journals = self.env['account.journal'].search([('code', '!=', False)])

        return [(j.code, j.code) for j in journals]

    card_on_delivery_trigger_code = fields.Selection(
        selection=_get_journal_code_selection,
        string='Incoming Card Code (Trigger)',
        help="Select the short code (e.g. CRDOD) that identifies Card payments."
    )

    card_on_delivery_journal_id = fields.Many2one(
        'account.journal',
        string='Card on Delivery Journal',
        help='The journal where the payment will be recorded.'
    )

    mataa_discount_account_id = fields.Many2one(
        'account.account',
        string="Mataa Discount Account"
    )

    mataa_discount_label = fields.Char(
        string="Mataa Discount Label",
        default="Marketing Discount (Coupon)",
        help="The description that will appear on the invoice line and journal items."
    )

    mataa_shipping_discount_account_id = fields.Many2one(
        'account.account',
        string="Shipping Discount Account",
        domain="[('deprecated', '=', False)]",
        help="The account where the shipping discount difference will be recorded."
    )

    mataa_shipping_discount_label = fields.Char(
        string="Shipping Discount Label",
        default="خصم توصيل (عروض)",
        help="The description that will appear on the invoice line for shipping discounts."
    )

