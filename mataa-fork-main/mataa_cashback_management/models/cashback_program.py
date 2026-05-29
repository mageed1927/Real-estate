# -*- coding: utf-8 -*-
from odoo import fields, models

class CashbackProgram(models.Model):
    _name = 'cashback.program'
    _description = 'Cashback Program'

    name = fields.Char(string="Program Name", required=True)
    active = fields.Boolean(default=True)
    start_date = fields.Date(string="Start Date", required=True)
    end_date = fields.Date(string="End Date", required=True)

    cashback_percentage = fields.Float(
        string="Cashback Percentage (%)",
        required=True,
        help="The percentage of the eligible amount to be given back to the customer."
    )

    creation_method = fields.Selection(
        [
            ('payment', 'Create Payment from Journal'),
            ('journal_entry', 'Create Manual Journal Entry')
        ],
        string="Creation Method",
        default='payment',
        required=True
    )

    journal_id = fields.Many2one(
        'account.journal',
        string="Payment Journal",
        domain="[('type', 'in', ('bank', 'cash'))]",
        help="The journal used to create the wallet payment for the customer."
    )

    entry_journal_id = fields.Many2one(
        'account.journal',
        string="Journal for Entry",
        domain="[('type', '=', 'general')]",
        help="The Miscellaneous Operations journal to post the entry."
    )
    expense_account_id = fields.Many2one(
        'account.account',
        string="Expense Account",
        help="The expense account that will bear the cost of this cashback."
    )

    tag_to_apply_id = fields.Many2one(
        'so.tag',
        string="Tag to Apply",
        help="This tag will be automatically added to the sales order if it benefits from this cashback program."
    )

    activity_user_id = fields.Many2one(
        'res.users',
        string="Responsible for Approval",
        help="The user who will be assigned the activity to approve cashback for partially delivered orders."
    )
    helpdesk_team_id = fields.Many2one(
        'helpdesk.team',
        string="Helpdesk Team",
        help="The helpdesk team to which the approval ticket will be sent."
    )

    rule_ids = fields.One2many(
        'cashback.program.rule',
        'program_id',
        string="Rules & Conditions"
    )

    usage_limit_per_customer = fields.Integer(
        string="Usage Limit Per Customer",
        default=0,
        help="Maximum number of times this program can be used by a single customer. Set to 0 for unlimited."
    )