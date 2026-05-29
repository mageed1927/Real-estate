# -*- coding: utf-8 -*-

from odoo import api, fields, models


class AccountInvoiceReport(models.Model):
    _inherit = "account.invoice.report"

    mataa_product_cost_subtotal = fields.Float(string='Product Subtotal Cost', readonly=True)


    @api.model
    def _select(self):
        select_str = super()._select()
        select_str += """
            ,line.mataa_product_cost_subtotal * (CASE WHEN move.move_type IN ('in_invoice','out_refund','in_receipt') THEN -1 ELSE 1 END)
                                                                            AS mataa_product_cost_subtotal
            """
        return select_str
