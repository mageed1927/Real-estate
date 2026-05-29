# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError



class StockScrap(models.Model):
    _inherit = 'stock.scrap'

    responsible_partner_id = fields.Many2one("res.partner", string="Responsible Partner",
                                             help = "Specifies the partner to whom the scrap operation cost will be assigned. If left empty, the cost will be assigned to the company by default.")
    mataa_analytic_account_id = fields.Many2one("account.analytic.account", string="Analytic Account",
                                                help="Used only when the scrap cost is assigned to the company. This analytic account will be set on the expense journal entry line.")

    def do_scrap(self):
        for scrap in self:
            super(StockScrap, self.with_context(scrap_responsible_partner_id=scrap.responsible_partner_id.id, scrap_analytic_account_id=scrap.mataa_analytic_account_id.id)).do_scrap()
        return True
