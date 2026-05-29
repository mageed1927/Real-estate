from odoo.http import request


class ExternalApiConfig:

    @staticmethod
    def get_env():
        return request.env if request else None

    @staticmethod
    def get_external_api_order_management_url(env=None):
        if not env:
            env = ExternalApiConfig.get_env()
        url = env['ir.config_parameter'].sudo().get_param('mataa_external_sync.external_api_base_url') + "/OrderManagement"
        return url

    @staticmethod
    def get_wallet_api_url(env=None):
        if not env:
            env = ExternalApiConfig.get_env()
        url = env['ir.config_parameter'].sudo().get_param('mataa_order_management.wallet_api_base_url') + "/api/v1/Wallet"
        return url

    @staticmethod
    def get_transaction_api_url(env=None):
        if not env:
            env = ExternalApiConfig.get_env()
        url = env['ir.config_parameter'].sudo().get_param('mataa_order_management.wallet_api_base_url') + "/api/v1/transaction"
        return url

    @staticmethod
    def get_external_api_base_url():
        return request.env['ir.config_parameter'].sudo().get_param('mataa_order_management.dtrack_api_base_url')
    
    @staticmethod
    def get_api_key():
        return request.env['ir.config_parameter'].sudo().get_param('mataa_order_management.dtrack_api_key')

    @staticmethod
    def get_vendor_notification_webhook():
        return request.env['ir.config_parameter'].sudo().get_param('mataa_order_management.vendor_notification_webhook')
