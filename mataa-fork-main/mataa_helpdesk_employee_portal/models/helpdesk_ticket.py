# -*- coding: utf-8 -*-
from odoo import models, fields

class HelpdeskTicket(models.Model):
    _inherit = 'helpdesk.ticket'

    employ = fields.Many2one('hr.employee', string='Assigned Employee')