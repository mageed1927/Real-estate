
from odoo.http import request
from odoo.exceptions import UserError

class ExternalApiConfig:

    @staticmethod
    def get_env():
        return request.env if request else None

    @staticmethod
    def get_external_api_catalog_management_url(env=None):
        if not env:
            env = ExternalApiConfig.get_env()
        try:
            url = env['ir.config_parameter'].sudo().get_param('mataa_external_sync.external_api_base_url') + "/CatalogManagement"
            return url
        except:
            raise UserError("External Api Base Url not found")

