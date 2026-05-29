import base64
import json

from requests.auth import HTTPBasicAuth

from ..constants.sale_order_state_mapping import MATAA_STATE_REVERSE_MAPPING
from odoo import api, models
import requests
from odoo.http import request
from odoo.exceptions import UserError
from ..constants.external_api_config import ExternalApiConfig

from odoo.addons.mataa_external_sync.utilities.external_auth import ExternalAuthUtil


class SaleOrderSyncService:
    @staticmethod
    def update_status(target_id, status):
        external_status = MATAA_STATE_REVERSE_MAPPING.get(status)

        url = f"{ExternalApiConfig.get_external_api_order_management_url()}/api/v1/Order/{target_id}/ChangeOrderState?Status={external_status}"

        response = requests.put(url, json={}, headers=ExternalAuthUtil.get_auth_headers(), verify=False)

        try:
            response.raise_for_status()
            return {'status': 'success', 'response_text': response.text}
            # return response.json()
        except requests.exceptions.HTTPError as err:
            raise UserError(f"Error updating order status to Order-Management-System: {json.loads(err.response.content.decode('utf-8')).get('message')}")
            return None

    @staticmethod
    def send_so_update(order_id, payload):
        url = f"{ExternalApiConfig.get_external_api_order_management_url()}/api/v1/Order/updateDetails/mataaOrderNumber/{order_id}"
        expected_api_key = request.env['ir.config_parameter'].sudo().get_param('mataa_order_management.external_api_token')
        headers = {'Content-Type': 'application/json','Api-Token': expected_api_key}
        try:
            response = requests.put(url, json=payload, headers=headers, timeout=10)
            response.raise_for_status()
        except requests.exceptions.HTTPError as err:
            raise UserError(
                f"SO API Sync Error in update order: {json.loads(err.response.content.decode('utf-8')).get('message')}")
        return None

    @staticmethod
    def update_payment_details(order_id, payload):
        """
        This method sends payment-specific updates to the new dedicated endpoint.
        """
        url = f"{ExternalApiConfig.get_external_api_order_management_url()}/api/v1/Order/by-mataaOrderNumber/{order_id}"

        expected_api_key = request.env['ir.config_parameter'].sudo().get_param(
            'mataa_order_management.external_api_token')
        headers = {'Content-Type': 'application/json', 'Api-Token': expected_api_key}

        try:
            response = requests.put(url, json=payload, headers=headers, timeout=10)
            response.raise_for_status()
        except requests.exceptions.HTTPError as err:
            raise UserError(
                f"Payment Update API Sync Error: {json.loads(err.response.content.decode('utf-8')).get('message')}")
        except requests.exceptions.RequestException as e:
            raise UserError(f"Payment Update Connection Error: {e}")
        return None