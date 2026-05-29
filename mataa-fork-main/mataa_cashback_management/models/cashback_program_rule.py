# -*- coding: utf-8 -*-
from odoo import fields, models

class CashbackProgramRule(models.Model):
    _name = 'cashback.program.rule'
    _description = 'Cashback Program Rule'

    program_id = fields.Many2one('cashback.program', string="Program", required=True, ondelete='cascade')


    product_ids = fields.Many2many(
        'product.product',
        string="Specific Products"
    )
    category_id = fields.Many2one(
        'product.category',
        string="Internal Category"
    )
    partner_ids = fields.Many2many(
        comodel_name='res.partner',
        relation='cashback_rule_customer_rel',
        string="Specific Customers"
    )


    brand_ids = fields.Many2many(
        comodel_name='product.brand',
        relation='cashback_rule_brand_rel',
        string="Specific Brands"
    )

    public_categ_ids = fields.Many2many(
        comodel_name='product.public.category',
        relation='cashback_rule_pub_categ_rel',
        string="Website Categories"
    )

    vendor_ids = fields.Many2many(
        comodel_name='res.partner',
        relation='cashback_rule_vendor_rel',
        string="Specific Vendors",
        domain="[('supplier_rank', '>', 0)]"
    )

    minimum_amount = fields.Float(
        string="Minimum Purchase Amount",
        default=0.0
    )

