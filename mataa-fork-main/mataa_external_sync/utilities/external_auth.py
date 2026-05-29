import base64
from ..constants.external_api_config import ExternalApiConfig
from odoo.http import request


class ExternalAuthUtil:
    @staticmethod
    def get_auth_headers(env=None):
        # TODO: change/remove these after new product catalog system integration
        # encoded_credentials = base64.b64encode(
        #     f"{ExternalApiConfig.get_customer_key(env)}:{ExternalApiConfig.get_customer_secret(env)}".encode('utf-8')).decode("ascii")
        expected_api_key = request.env['ir.config_parameter'].sudo().get_param('mataa_order_management.external_api_token')
        headers = {
            "Content-Type": "application/json",
            "accept": "*/*",
            'Api-Token': expected_api_key
            # "Authorization": f"Basic {encoded_credentials}"
        }

        return headers
