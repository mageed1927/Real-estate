import requests

from odoo.exceptions import UserError
from ..constants.external_api_config import ExternalApiConfig
from ..utilities.external_auth import ExternalAuthUtil
import logging

class VendorNotificationService:
    @staticmethod
    def notify_new_rfq_created(vendor_id, rfq_id):
        url = f"{ExternalApiConfig.get_vendor_notification_webhook()}"

        target_data = {
            "vendorId": vendor_id,
            "title": "new rfq created",
            "message": f"rfq_id : {rfq_id}"
        }

        try:
            response = requests.put(url, json=target_data, headers=ExternalAuthUtil.get_vdm_auth_headers(), verify=False)
            response.raise_for_status()
            return True
        except Exception as err:
            logging.error(f"Failed to notify vendor {vendor_id} about RFQ {rfq_id}: {err}")
            return False
