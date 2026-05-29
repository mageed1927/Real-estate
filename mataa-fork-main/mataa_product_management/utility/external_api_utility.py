import base64
from odoo.http import request
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)


class ExternalAuthUtil:
    @staticmethod
    def get_auth_headers(env=None):
        expected_api_key = request.env['ir.config_parameter'].sudo().get_param('mataa_order_management.external_api_token')
        headers = {
            "Content-Type": "application/json",
            "accept": "*/*",
            'Api-Token': expected_api_key
        }

        return headers


    @staticmethod
    def get_error_arhive(response):
        if response.status_code == 404:
            raise UserError(f"The Product is not found in EMS.")
        if response.status_code == 500:
            _logger.info(f"EMS ERROR: {response}")
            raise UserError(f"There is an issue when archiving the product. Error: EMS returned 500 error.")
        _logger.info(f"EMS ERROR: {response}")
        raise UserError(f"There is an issue when archiving the product. Please try again.")

