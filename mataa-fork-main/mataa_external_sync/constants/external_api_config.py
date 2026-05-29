from odoo import api, SUPERUSER_ID
from odoo.http import request


class ExternalApiConfig:

    @staticmethod
    def get_env():
        return request.env if request else None

    @staticmethod
    def get_external_api_catalog_management_url(env=None):
        if not env:
            env = ExternalApiConfig.get_env()
        url = env['ir.config_parameter'].sudo().get_param('mataa_external_sync.external_api_base_url') + "/CatalogManagement"
        return url

    @staticmethod
    def get_external_api_user_management_url(env=None):
        if not env:
            env = ExternalApiConfig.get_env()
        url = env['ir.config_parameter'].sudo().get_param('mataa_external_sync.external_api_base_url') + "/UserManagement"
        return url

    @staticmethod
    def get_customer_key(env=None):
        # TODO: change/remove these after new product catalog system integration
        if not env:
            env = ExternalApiConfig.get_env()
        return env['ir.config_parameter'].sudo().get_param('mataa_external_sync.customer_key')

    @staticmethod
    def get_customer_secret(env=None):
        # TODO: change/remove these after new product catalog system integration
        if not env:
            env = ExternalApiConfig.get_env()
        return env['ir.config_parameter'].sudo().get_param('mataa_external_sync.customer_secret')
