# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError
from ...mataa_s3.services.s3_service import S3Service
from ..utility.image_utility import ImageUtility
from ..utility.file_utility import FileUtility
from ..constants.image_constants import IMAGE_SIZES


class VendorCreditDifferenceTracker(models.Model):
    _name = 'vendor.credit.difference.tracker'
    _description = 'Vendor Credit Difference Tracker'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    vendor_id = fields.Many2one('res.partner', readonly=True, tracking=True)

    difference_amount = fields.Float(readonly=True, tracking=True, help="If positive then the products cost increased")

    account_move_id = fields.Many2one('account.move', readonly=True, tracking=True)

    @api.model
    def track_difference(self, vendor_id, amount):
        tracker_id = self.search([('vendor_id', '=', vendor_id), ('account_move_id', '=', False)], limit=1)
        if tracker_id:
            tracker_id.difference_amount = tracker_id.difference_amount + amount
        else:
            self.create({'vendor_id': vendor_id, 'difference_amount': amount})

    def creat_difference_entry(self):
        for tracker_id in self.filtered(lambda t: not t.account_move_id and t.difference_amount != 0):
            company_id = self.env.company
            if tracker_id.difference_amount > 0:
                move_vals = {
                    'journal_id': company_id.inhouse_difference_journal_id.id,
                    'company_id': company_id.id,
                    'ref': 'In-House Cost Update',
                    'move_type': 'entry',
                    'line_ids': [(0, 0, {
                        'name': 'Cost changed',
                        'account_id': company_id.inhouse_difference_value_account_id.id,
                        'debit': abs(tracker_id.difference_amount),
                        'credit': 0,
                        'quantity': 0,
                    }), (0, 0, {
                        'name': 'Cost changed',
                        'account_id': tracker_id.vendor_id.property_account_payable_id.id,
                        'debit': 0,
                        'credit': abs(tracker_id.difference_amount),
                        'partner_id': tracker_id.vendor_id.id,
                    })],
                }
            else:
                move_vals = {
                    'journal_id': company_id.inhouse_difference_journal_id.id,
                    'company_id': company_id.id,
                    'ref': 'In-House Cost Update',
                    'move_type': 'entry',
                    'line_ids': [(0, 0, {
                        'name': 'Cost changed',
                        'account_id': tracker_id.vendor_id.property_account_payable_id.id,
                        'debit': abs(tracker_id.difference_amount),
                        'credit': 0,
                        'partner_id': tracker_id.vendor_id.id,
                    }), (0, 0, {
                        'name': 'Cost changed',
                        'account_id': company_id.inhouse_difference_value_account_id.id,
                        'debit': 0,
                        'credit': abs(tracker_id.difference_amount),
                    })],
                }
            move_id = self.env['account.move'].create(move_vals)
            tracker_id.account_move_id = move_id
