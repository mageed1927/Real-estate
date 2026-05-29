import json
from odoo.exceptions import UserError
from ..constants.external_api_config import ExternalApiConfig
from ..utilities.external_auth import ExternalAuthUtil
import base64
import requests


class AttributeValueSyncService:
    @staticmethod
    def get_by_id(target_id):
        url = f"{ExternalApiConfig.get_external_api_catalog_management_url()}/api/v1/Attributes/by-odooId/{target_id}"

        try:
            response = requests.get(url, headers=ExternalAuthUtil.get_auth_headers(), verify=False)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as err:
            raise UserError(
                f"Error Fetching attribute_value from Product-Catalog: {json.loads(err.response.content.decode('utf-8'))}")

    @staticmethod
    def create(target_data):
        url = f"{ExternalApiConfig.get_external_api_catalog_management_url()}/api/v1/Attributes/create/by-odooId"

        response = requests.post(url, json=target_data, headers=ExternalAuthUtil.get_auth_headers(), verify=False)

        try:
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as err:
            raise UserError(f"Error creating attribute_value to Product-Catalog: {json.loads(err.response.content.decode('utf-8'))}")

    @staticmethod
    def update(target_id, target_data):
        url = f"{ExternalApiConfig.get_external_api_catalog_management_url()}/api/v1/Attributes/update/by-odooId?OdooId={target_id}"

        response = requests.put(url, json=target_data, headers=ExternalAuthUtil.get_auth_headers(), verify=False)

        try:
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as err:
            raise UserError(f"Error updating attribute_value to Product-Catalog: {json.loads(err.response.content.decode('utf-8'))}")

    @staticmethod
    def delete(target_id):
        url = f"{ExternalApiConfig.get_external_api_catalog_management_url()}/api/v1/Attributes/delete/by-odooId/{target_id}"

        response = requests.delete(url, headers=ExternalAuthUtil.get_auth_headers(), verify=False)

        try:
            response.raise_for_status()
            # return response.json()
        except requests.exceptions.HTTPError as err:
            raise UserError(f"Error syncing attribute_value to Product-Catalog: {json.loads(err.response.content.decode('utf-8'))}")