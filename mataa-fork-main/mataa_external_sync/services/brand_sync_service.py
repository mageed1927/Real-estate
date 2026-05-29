import base64
import json
import requests

from odoo.exceptions import UserError
from ..constants.external_api_config import ExternalApiConfig
from ..utilities.external_auth import ExternalAuthUtil


class BrandSyncService:
    @staticmethod
    def create(target_data):
        url = f"{ExternalApiConfig.get_external_api_catalog_management_url()}/api/v1/Brand/create/by-odooId"

        response = requests.post(url, json=target_data, headers=ExternalAuthUtil.get_auth_headers(), verify=False)

        try:
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as err:
            raise UserError(f"Error creating brand {target_data.get('name')} to Product-Catalog: {json.loads(err.response.content.decode('utf-8'))}")

    @staticmethod
    def update(target_id, target_data):
        url = f"{ExternalApiConfig.get_external_api_catalog_management_url()}/api/v1/Brand/update/by-odooId/{target_id}"

        response = requests.put(url, json=target_data, headers=ExternalAuthUtil.get_auth_headers(), verify=False)

        try:
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as err:
            raise UserError(f"Error updating brand {target_data.get('name')} in Product-Catalog: {json.loads(err.response.content.decode('utf-8'))}")

    @staticmethod
    def delete(target_id):
        url = f"{ExternalApiConfig.get_external_api_catalog_management_url()}/api/v1/Brand/delete/by-odooId/{target_id}"

        response = requests.delete(url, headers=ExternalAuthUtil.get_auth_headers(), verify=False)

        try:
            response.raise_for_status()
            # return response.json()
        except requests.exceptions.HTTPError as err:
            raise UserError(f"Error deleting brand {target_id} from Product-Catalog: {json.loads(err.response.content.decode('utf-8'))}")