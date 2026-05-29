import base64
import json
import logging
import requests

from odoo.exceptions import UserError
from ..constants.external_api_config import ExternalApiConfig
from ..utilities.external_auth import ExternalAuthUtil

_logger = logging.getLogger(__name__)


class ProductSyncService:
    @staticmethod
    def get_by_id(target_id, env=None):
        url = f"{ExternalApiConfig.get_external_api_catalog_management_url(env)}/api/v1/Product/by-odooId/{target_id}"

        try:
            response = requests.get(url, headers=ExternalAuthUtil.get_auth_headers(env), verify=False)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as err:
            raise UserError(
                f"Error Fetching product from Product-Catalog: {json.loads(err.response.content.decode('utf-8'))}")

    @staticmethod
    def create(target_data, env=None):
        url = f"{ExternalApiConfig.get_external_api_catalog_management_url(env)}/api/v1/Product/CreateWithDetails"
        response = requests.post(url, json=target_data, headers=ExternalAuthUtil.get_auth_headers(env), verify=False)

        try:
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as err:
            raise UserError(f"Error creating product to Product-Catalog: {json.loads(err.response.content.decode('utf-8'))}")

    @staticmethod
    def update(target_id, target_data, env=None):
        url = f"{ExternalApiConfig.get_external_api_catalog_management_url(env)}/api/v1/Product/update/by-odooId/{target_id}"
        response = requests.put(url, json=target_data, headers=ExternalAuthUtil.get_auth_headers(env), verify=False)
        try:
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as err:
            raise UserError(f"Error updating product to Product-Catalog: {json.loads(err.response.content.decode('utf-8'))}")

    @staticmethod
    def batch_update(target_datas, env=None):
        # TODO : after the new product catalog the batch update needs fixing
        # url = f"{ExternalApiConfig.get_external_api_catalog_management_url(env)}/wc/v3/products/batch"
        # response = requests.put(url, json=target_datas, headers=ExternalAuthUtil.get_auth_headers(env), verify=False)
        # try:
        #     response.raise_for_status()
        #     _logger.info('Mataa: IDs of syncing product template %s ', [p.get('sku') for p in target_datas.get('update', [])])
        #     return response.json()
        # except requests.exceptions.HTTPError as err:
        #     raise UserError(f"Error updating products to Product-Catalog: {json.loads(err.response.content.decode('utf-8'))}")
        pass

    @staticmethod
    def update_json(json_batch, products_dto, type="update"):
        # TODO : after the new product catalog the batch update needs fixing
        # json_batch.update({
        #     type: products_dto
        # })
        # return json_batch
        pass

    @staticmethod
    def delete(target_id, env=None):
        url = f"{ExternalApiConfig.get_external_api_catalog_management_url(env)}/api/v1/Product/delete-by-odooId/{target_id}"

        response = requests.delete(url, headers=ExternalAuthUtil.get_auth_headers(env), verify=False)

        try:
            response.raise_for_status()
            # return response.json()
        except requests.exceptions.HTTPError as err:
            raise UserError(f"Error syncing product to Product-Catalog: {json.loads(err.response.content.decode('utf-8'))}")

    @staticmethod
    def create_with_details_v2(target_data, env=None):
        url = f"{ExternalApiConfig.get_external_api_catalog_management_url(env)}/api/v1/Product/CreateWithDetailsV2"
        
        response = requests.post(url, json=target_data, headers=ExternalAuthUtil.get_auth_headers(env), verify=False)

        try:
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as err:
            raise UserError(f"Error creating product with details to Product-Catalog: {json.loads(err.response.content.decode('utf-8'))}")