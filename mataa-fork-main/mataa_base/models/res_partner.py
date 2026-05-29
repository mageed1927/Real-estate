# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from dateutil.relativedelta import relativedelta

from odoo.exceptions import UserError


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # This redefines the existing sale_order_count field to make it stored
    sale_order_count = fields.Integer(
        compute='_compute_sale_order_count',
        store=False,
        search='_search_sale_order_count'
    )

    mataa_id = fields.Char(string="Mataa ID", readonly=True)

    vendor_category_id = fields.Many2many('product.public.category' , string="Vendor Category")

    birthdate_date = fields.Date("Birthdate")
    age = fields.Integer(readonly=True, compute="_compute_age")
    gender = fields.Selection([
        ("male", "Male"),
        ("female", "Female"),
        ("other", "Other")
    ])

    brand_ids = fields.Many2many(
        comodel_name='product.brand',
        relation='brand_vendor_rel',
        column1='partner_id',
        column2='brand_id',
        string='Brands'
    )
    brand_count = fields.Integer(compute="_compute_brand_count")

    is_customer = fields.Boolean(
        string='Is a Customer',
        compute='_compute_is_customer',
        inverse='_inverse_is_customer',
        store=False,
        help="Check this box to mark the partner as a customer (sets Customer Rank to 1 if 0)."
    )
    is_supplier = fields.Boolean(
        string='Is a Supplier',
        compute='_compute_is_supplier',
        inverse='_inverse_is_supplier',
        store=False,
        help="Check this box to mark the partner as a supplier (sets Supplier Rank to 1 if 0)."
    )

    wallet_amount = fields.Float(string='Wallet Balance', compute='_compute_wallet_amount')

    @api.model_create_multi
    def create(self, vals):
        for val in vals:
            if val.get('is_supplier') == 0 and val.get('is_customer') == 0 and not val.get('is_employee'):
                raise UserError("Contact type must be either supplier, customer or employee")
        return super(ResPartner, self).create(vals)
    def _search_sale_order_count(self, operator, value):
        query = f"""
            SELECT partner_id 
            FROM sale_order 
            WHERE state IN ('sale','cancel', 'done')
            AND (active IS NULL OR active = TRUE)
            GROUP BY partner_id 
            HAVING COUNT(*) {operator} %s
        """

        self.env.cr.execute(query, (value,))
        ids = [row[0] for row in self.env.cr.fetchall()]

        if operator == '=' and value == 0:
            return [('id', 'not in', ids)]

        return [('id', 'in', ids)]

    def _compute_wallet_amount(self):
        for partner in self:
            partner.wallet_amount = partner.wallet_amount or 0.0

    @api.depends('customer_rank')
    def _compute_is_customer(self):
        for partner in self:
            partner.is_customer = partner.customer_rank > 0

    @api.depends('supplier_rank')
    def _compute_is_supplier(self):
        for partner in self:
            partner.is_supplier = partner.supplier_rank > 0

    def _inverse_is_customer(self):
        for partner in self:
            if partner.is_customer:
                partner.customer_rank = 1
            else:
                partner.customer_rank = 0

    def _inverse_is_supplier(self):
        for partner in self:
            if partner.is_supplier:
                partner.supplier_rank = 1
            else:
                partner.supplier_rank = 0

    @api.depends('brand_ids')
    def _compute_brand_count(self):
        for rec in self:
            rec.brand_count = len(rec.brand_ids)

    def action_view_related_brands(self):
        self.ensure_one()
        if len(self.brand_ids) == 1:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Related Brands'),
                'res_model': 'product.brand',
                'view_mode': 'form',
                'res_id': self.brand_ids.id,
                'target': 'current',
            }
        elif len(self.brand_ids) > 1:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Related Brands'),
                'res_model': 'product.brand',
                'view_mode': 'tree,form',
                'domain': [('id', 'in', self.brand_ids.ids)],
                'target': 'current',
            }

    @api.constrains('mataa_id')
    def _check_unique_mataa_id(self):
        for record in self:
            if record.mataa_id:
                domain = [
                    ('mataa_id', '=', record.mataa_id),
                    ('id', '!=', record.id)
                ]

                if record.supplier_rank > 0:
                    domain.append(('supplier_rank', '>', 0))
                elif record.customer_rank > 0:
                    domain.append(('customer_rank', '>', 0))
                else:
                    domain.append([('supplier_rank', '=', 0), ('customer_rank', '=', 0)])

                existing_partner = self.search(domain=domain)
                if existing_partner:
                    raise UserError(
                        f"The following mataa_id: {record.mataa_id} was found in other partners. \n"
                        "Note that partner mataa_id should not repeat."
                    )

    @api.depends("birthdate_date")
    def _compute_age(self):
        for record in self:
            age = 0
            if record.birthdate_date:
                age = relativedelta(fields.Date.today(), record.birthdate_date).years
            record.age = age

    def action_open_customer_payment(self):
        self.ensure_one()

        if not self.is_customer:
            self.is_customer = True

        return {
            'name': _('Customer Payment'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.payment',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_payment_type': 'inbound',
                'default_partner_type': 'customer',
                'default_partner_id': self.id,
            },
        }
