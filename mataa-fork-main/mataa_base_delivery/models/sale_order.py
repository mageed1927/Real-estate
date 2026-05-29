# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = "sale.order"

    mataa_city_id = fields.Many2one('mataa.city', string='Area')
    mataa_parent_city_id = fields.Many2one('mataa.city', string='City', compute='_compute_parent_city', store=True)

    # Informational Fields Regarding "billing Address"
    mata_billing_first_name = fields.Char(tracking=True, copy=False)
    mata_billing_last_name = fields.Char(tracking=True, copy=False)
    mata_billing_address_1 = fields.Char(tracking=True, copy=False)
    mata_billing_address_2 = fields.Char(tracking=True, copy=False)
    mata_billing_company = fields.Char(tracking=True, copy=False)
    mata_billing_city = fields.Char(tracking=True, copy=False)
    mata_billing_state = fields.Char(tracking=True, copy=False)
    mata_billing_country = fields.Char(tracking=True, copy=False)
    mata_billing_phone = fields.Char(tracking=True, copy=False)
    mata_billing_postcode = fields.Char(tracking=True, copy=False)
    mata_billing_email = fields.Char(tracking=True, copy=False)
    mata_billing_link = fields.Char(tracking=True, copy=False)

    # Informational Fields Regarding "shipping Address"
    mata_shipping_first_name = fields.Char(tracking=True, copy=False)
    mata_shipping_last_name = fields.Char(tracking=True, copy=False)
    mata_shipping_address_1 = fields.Char(tracking=True, copy=False)
    mata_shipping_address_2 = fields.Char(tracking=True, copy=False)
    mata_shipping_company = fields.Char(tracking=True, copy=False)
    mata_shipping_city = fields.Char(tracking=True, copy=False)
    mata_shipping_state = fields.Char(tracking=True, copy=False)
    mata_shipping_country = fields.Char(tracking=True, copy=False)
    mata_shipping_phone = fields.Char(tracking=True, copy=False)
    mata_shipping_postcode = fields.Char(tracking=True, copy=False)
    mata_shipping_email = fields.Char(tracking=True, copy=False)
    mata_shipping_link = fields.Char(tracking=True, copy=False)

    @api.depends('mataa_city_id', 'mataa_city_id.parent_id')
    def _compute_parent_city(self):
        for order in self:
            order.mataa_parent_city_id = order.mataa_city_id.parent_id or order.mataa_city_id


    def action_confirm(self):
        for order in self:
            if not order.mataa_city_id:
                raise UserError(_('You must select a city first.'))
        return super(SaleOrder, self).action_confirm()

    def get_shipment_price(self):
        # Override this method to calculate the Cash On Delivery price
        return 0.0

    def get_customer_phone(self):
        self.ensure_one()
        # Override this method to in carrier modules in order to reformat the phone number
        return self.mata_billing_phone or self.mata_shipping_phone or self.partner_id.phone or ""

    def get_customer_phone_2(self):
        self.ensure_one()
        # Override this method to in carrier modules in order to reformat the phone number
        return self.mata_billing_address_2 or self.mata_shipping_address_2 or self.partner_id.phone or ""

    def close_mataa_order(self, shipment_status):
        # shipment_status: 'fully_delivered', 'partially_delivered', 'fully_returned'
        self.ensure_one()
        if shipment_status == 'fully_delivered':
            self.close_fully_delivered_order()
        elif shipment_status == 'partially_delivered':
            self.close_partially_delivered_order()
        elif shipment_status == 'fully_returned':
            self.close_fully_returned_order()
        else:
            raise UserError(_('You must select a valid final shipment status.'))

    def close_fully_delivered_order(self):
        # Override this method to close a fully delivered order
        return

    def close_partially_delivered_order(self):
        # Override this method to close a partially delivered order
        return

    def close_fully_returned_order(self):
        # Override this method to close a fully returned order
        return