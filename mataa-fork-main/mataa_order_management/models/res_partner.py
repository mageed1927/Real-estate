# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
import datetime
from odoo.http import request
from ..services.vms_service import VMSService


class ResPartner(models.Model):
    _inherit = 'res.partner'

    is_deleted = fields.Boolean(string="Deleted", default=False)
    blanket_order_qty_limit = fields.Integer(
        string="Blanket Order Quantity Limit"
    )
    min_amount = fields.Integer('Minimum amount')

    working_hours_start = fields.Float(string="Working Hours Start")
    working_hours_end = fields.Float(string="Working Hours End")
    vendor_status = fields.Selection([
        ('ongoing', 'Ongoing cooperation with us'),
        ('stopped', 'Stopped cooperating with us'),
        ('partial', 'Partially stopped (for a period and will return)')
    ], string='Vendor Status', default='ongoing')

    payment_due_days = fields.Char(
        string="Payment Due Days",
        help="Enter the day(s) of the month for payment. For multiple days, separate them with a comma, e.g., 15,30"
    )
    is_payment_due_today = fields.Boolean(
        string="Is Payment Due Today?",
        compute='_compute_is_payment_due_today',
        search='_search_is_payment_due_today'
    )

    payment_policy_desc = fields.Char(
        string="Payment Policy Description",
        help="Description of payment policy for the finance team (e.g., 'Every Saturday', 'After 2 Bills')"
    )

    last_payment_date = fields.Date(string="Last Payment Date")
    last_matching_date = fields.Date(string="Last Matching Date")

    def _compute_is_payment_due_today(self):
        """
        Calculates if the payment for the partner is due today.
        This is not stored and computed on the fly.
        """
        today_day = datetime.date.today().day
        for partner in self:
            partner.is_payment_due_today = False
            if partner.payment_due_days:
                try:
                    due_days = [int(day.strip()) for day in partner.payment_due_days.split(',')]
                    if today_day in due_days:
                        partner.is_payment_due_today = True
                except (ValueError, AttributeError):

                    partner.is_payment_due_today = False

    @api.model
    def _search_is_payment_due_today(self, operator, value):
        """
        This method allows searching on the computed field 'is_payment_due_today'.
        It finds all suppliers whose payment is due today and returns their IDs.
        """
        if operator != '=' or not isinstance(value, bool):
            return []

        today_day = datetime.date.today().day

        all_suppliers = self.search([
            ('supplier_rank', '>', 0),
            ('payment_due_days', '!=', False)
        ])

        matching_ids = []
        for partner in all_suppliers:
            try:
                due_days = [int(day.strip()) for day in partner.payment_due_days.split(',')]
                if today_day in due_days:
                    matching_ids.append(partner.id)
            except (ValueError, AttributeError):
                continue

        if value:
            return [('id', 'in', matching_ids)]
        else:
            return [('id', 'not in', matching_ids)]

    @api.model
    def _cron_check_vendor_payment_due(self):
        """
        This method is called by a daily cron job.
        It checks for vendors whose payment is due today and creates an activity
        for the users specified in the settings.
        """
        today_day = datetime.date.today().day
        notification_users = self.env.company.payment_due_notification_user_ids
        if not notification_users:
            return

        vendors = self.search([
            ('supplier_rank', '>', 0),
            ('payment_due_days', '!=', False)
        ])

        activity_type_id = self.env.ref('mail.mail_activity_data_todo').id
        vendors_due_today = []
        for vendor in vendors:
            try:
                due_days = [int(day.strip()) for day in vendor.payment_due_days.split(',')]
                if today_day in due_days:
                    vendors_due_today.append(vendor)
            except (ValueError, AttributeError):
                continue

        if not vendors_due_today:
            return

        vendor_names = ', '.join([v.name for v in vendors_due_today])
        note = _('The following vendors have payments due today: %s') % vendor_names

        for user in notification_users:
            self.env['mail.activity'].create({
                'res_id': user.partner_id.id,
                'res_model_id': self.env['ir.model']._get('res.partner').id,
                'activity_type_id': activity_type_id,
                'summary': _('Vendor Payments Due Today'),
                'note': note,
                'user_id': user.id,
                'date_deadline': datetime.date.today(),
            })
        return True
    @api.model_create_multi
    def create(self, vals):
        if isinstance(vals, list):
            # If vals is a list, process each item
            for record in vals:
                record['blanket_order_qty_limit'] = self.env['ir.config_parameter'].sudo().get_param(
                    'mataa_order_management.blanket_order_qty_limit')

                partners = super(ResPartner, self.with_context(from_create=True)).create(vals)
                for partner in partners:
                    if partner.supplier_rank >= 1 and partner.customer_rank == 0:
                        VMSService.create_vendor_in_vms(self.env, partner,is_updated=False)
                return partners
        else:
            # If vals is a single dictionary
            vals['blanket_order_qty_limit'] = self.env['ir.config_parameter'].sudo().get_param(
                'mataa_order_management.blanket_order_qty_limit')
            return super(ResPartner, self.with_context(from_create=True)).create(vals)


    def write(self, vals):
        res = super().write(vals)
        if self.env.context.get('from_create'):
            return res

        for partner in self:
            if partner.supplier_rank >= 1 and partner.customer_rank == 0:
                VMSService.create_vendor_in_vms(self.env,partner,is_updated=True)
        return res

    def unlink(self):
        for partner in self:
            if partner.supplier_rank > 0:
                partner.soft_delete()
            else:
                super(ResPartner, partner).unlink()

    def soft_delete(self):
        self.write({'is_deleted': True})

    def undo_soft_delete(self):
        self.write({'is_deleted': False})

    def check_quantity(self, qty):
        """
        Check qty to import regarding minimum amount
        """
        if self.min_amount > qty:
            return 0
        return qty

    def action_archive(self):
        for partner in self:
            VMSService.create_vendor_in_vms(self.env, partner, is_updated=True)
        return super().action_archive()

    def action_unarchieve(self):
        for partner in self:
            VMSService.create_vendor_in_vms(self.env, partner, is_updated=True)
        return super().action_unarchieve()
