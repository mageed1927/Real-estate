# -*- coding: utf-8 -*-
from odoo import models, api, _, fields


class PartnerLedgerCustomHandler(models.AbstractModel):
    _inherit = 'account.partner.ledger.report.handler'

    def _custom_options_initializer(self, report, options, previous_options=None):
        super()._custom_options_initializer(report, options, previous_options=previous_options)

        if any(col.get('expression_label') == 'payment_policy_desc' for col in options['columns']):
            return

        col_group_key = options['columns'][0].get('column_group_key')

        custom_columns = [
            {'name': _("Payment Policy"), 'expression_label': 'payment_policy_desc', 'column_group_key': col_group_key,
             'sortable': False, 'figure_type': 'string'},
            {'name': _("Last Payment Date"), 'expression_label': 'last_payment_date', 'column_group_key': col_group_key,
             'sortable': False, 'figure_type': 'date'},
            {'name': _("Last Matching Date"), 'expression_label': 'last_matching_date',
             'column_group_key': col_group_key, 'sortable': False, 'figure_type': 'date'}
        ]

        for col in reversed(custom_columns):
            options['columns'].insert(0, col)

    def _get_additional_column_aml_values(self):
        base_cols = super()._get_additional_column_aml_values()
        return f"{base_cols} '' AS payment_policy_desc, NULL::date AS last_payment_date, NULL::date AS last_matching_date, "

    def _get_report_line_partners(self, options, partner, partner_values, level_shift=0):
        res = super()._get_report_line_partners(options, partner, partner_values, level_shift=level_shift)


        policy_text = partner.payment_policy_desc or '' if partner else ''
        last_payment_text = str(partner.last_payment_date) if partner and partner.last_payment_date else ''
        last_matching_text = str(partner.last_matching_date) if partner and partner.last_matching_date else ''

        report = self.env['account.report'].browse(options['report_id'])
        for i, col in enumerate(options['columns']):
            expr = col.get('expression_label')
            if expr == 'payment_policy_desc':
                res['columns'][i] = report._build_column_dict(policy_text, col, options=options)
            elif expr == 'last_payment_date':
                res['columns'][i] = report._build_column_dict(last_payment_text, col, options=options)
            elif expr == 'last_matching_date':
                res['columns'][i] = report._build_column_dict(last_matching_text, col, options=options)

        return res
