import base64
import json
import requests

from odoo.exceptions import UserError
from ..constants.external_api_config import ExternalApiConfig
from ..utilities.external_auth import ExternalAuthUtil
import logging

_logger = logging.getLogger(__name__)

class VariantSyncService:

    @staticmethod
    def get_by_id(target_id, env=None):
        url = f"{ExternalApiConfig.get_external_api_catalog_management_url(env)}/api/v1/ProductVariant/by-odooId/{target_id}"

        try:
            response = requests.get(url, headers=ExternalAuthUtil.get_auth_headers(env), verify=False , timeout=(5, 30))
            response.raise_for_status()
            return response.json() if response.content else None

        except requests.exceptions.RequestException as err:
            body = None
            status = getattr(err.response, "status_code", None)

            if err.response is not None:
                try:
                    body = err.response.json()
                except ValueError:
                    body = (err.response.text or "").strip()[:1500]

            raise UserError(f"Error fetching variant from Product-Catalog. status={status}, body={body}")

    @staticmethod
    def create(parent_id, target_data, env=None):
        url = f"{ExternalApiConfig.get_external_api_catalog_management_url(env)}/api/v1/ProductVariant/OperationCreate?ProductOdooId={parent_id}"

        response = requests.post(url, json=target_data, headers=ExternalAuthUtil.get_auth_headers(env), verify=False , timeout=(5, 30))

        try:
            response.raise_for_status()
            return response.json() if response.content else None
        except requests.exceptions.RequestException as err:
            body = None
            status = getattr(err.response, "status_code", None)

            if err.response is not None:
                try:
                    body = err.response.json()
                except ValueError:
                    body = (err.response.text or "").strip()[:1500]

            raise UserError(f"Error creating variant in Product-Catalog. status={status}, body={body}")



    @staticmethod
    def update(target_id, target_data, env=None):
        url = f"{ExternalApiConfig.get_external_api_catalog_management_url(env)}/api/v1/ProductVariant/update/by-odooId/{target_id}"

        _logger.info(f"updating variant {target_id}\n{target_data}")

        response = requests.put(url, json=target_data, headers=ExternalAuthUtil.get_auth_headers(env), verify=False ,timeout=(5, 30))

        try:
            response.raise_for_status()
            return response.json() if response.content else None
        except requests.exceptions.RequestException as err:
            body = None
            status = getattr(err.response, "status_code", None)

            if err.response is not None:
                try:
                    body = err.response.json()
                except ValueError:
                    body = (err.response.text or "").strip()[:1500]

            raise UserError(f"Error updating variant to Product-Catalog. status={status}, body={body}")

    @staticmethod
    def batch_update(target_datas, parent_id, env=None):
        # TODO : after the new product catalog the batch update needs fixing
        # url = f"{ExternalApiConfig.get_external_api_catalog_management_url(env)}/wc/v3/products/{parent_id}/variations/batch"
        # response = requests.put(url, json=target_datas, headers=ExternalAuthUtil.get_auth_headers(env), verify=False)
        # try:
        #     response.raise_for_status()
        #     _logger.info('Mataa: IDs of syncing product product %s ', [p.get('sku') for p in target_datas.get('update', [])])
        #     return response.json()
        # except requests.exceptions.HTTPError as err:
        #     raise UserError(f"Error updating variants to Product-Catalog: {json.loads(err.response.content.decode('utf-8'))}")
        pass

    @staticmethod
    def update_json(json_batch, variants_dto, type="update"):
        # TODO : after the new product catalog the batch update needs fixing
        # json_batch.update({
        #     type: variants_dto
        # })
        # return json_batch
        pass

    @staticmethod
    def delete(target_id, env=None):
        url = f"{ExternalApiConfig.get_external_api_catalog_management_url(env)}/api/v1/ProductVariant/delete-by-odooId/{target_id}"

        response = requests.delete(url, headers=ExternalAuthUtil.get_auth_headers(env), verify=False ,timeout=(5, 30))

        try:
            response.raise_for_status()
            return response.json() if response.content else None
        except requests.exceptions.RequestException as err:
            body = None
            status = getattr(err.response, "status_code", None)

            if err.response is not None:
                try:
                    body = err.response.json()
                except ValueError:
                    body = (err.response.text or "").strip()[:1500]

            raise UserError(f"Error deleting variant from Product-Catalog. status={status}, body={body}")


    @staticmethod
    def create_with_details_v2(parent_id,target_data, env=None):
        url = f"{ExternalApiConfig.get_external_api_catalog_management_url(env)}/api/v1/ProductVariant/OperationCreateV2?ProductOdooId={parent_id}"
        response = requests.post(url, json=target_data, headers=ExternalAuthUtil.get_auth_headers(env), verify=False)

        try:
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as err:
            raise UserError(f"Error creating variant with details to Product-Catalog: {json.loads(err.response.content.decode('utf-8'))}")