from odoo import models, api, fields
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    @api.model
    def action_detect_duplicate_payments_cron(self):
        """
        Scheduled Action to detect and draft potential duplicate payments
        created within a short time frame.
        """

        time_threshold = datetime.now() - timedelta(minutes=15)


        payments = self.search([
            ('state', '=', 'posted'),
            ('partner_type', '=', 'customer'),
            ('create_date', '>=', time_threshold),
            ('is_internal_transfer', '=', False)
        ], order='create_date desc')

        processed_ids = []

        for payment in payments:
            if payment.id in processed_ids:
                continue

            if payment.partner_id.is_supplier:
                continue


            duplicates = payments.filtered(lambda p:
                                           p.id != payment.id and
                                           p.partner_id == payment.partner_id and
                                           p.amount == payment.amount and
                                           p.currency_id == payment.currency_id and
                                           p.payment_type == payment.payment_type and
                                           not p.is_internal_transfer and
                                           abs((p.create_date - payment.create_date).total_seconds()) <= 120
                                           )

            if duplicates:
                for dup in duplicates:
                    if dup.id not in processed_ids:

                        if dup.partner_id.is_supplier:
                            processed_ids.append(dup.id)
                            continue

                        try:

                            dup.action_draft()

                            dup.message_post(
                                body="System Alert: Payment reset to Draft automatically due to potential duplicate detection.")

                            _logger.info(f"Duplicate payment detected and drafted: {dup.name} (ID: {dup.id})")
                        except Exception as e:
                            _logger.error(f"Failed to draft payment {dup.name}: {str(e)}")

                        processed_ids.append(dup.id)

                processed_ids.append(payment.id)