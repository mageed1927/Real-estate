# -*- coding: utf-8 -*-

import base64
import json
import logging
import requests

from odoo.exceptions import UserError
from ..constants.external_api_config import ExternalApiConfig
from ..utilities.external_auth import ExternalAuthUtil

_logger = logging.getLogger(__name__)


class ResPartnerSyncService:
    @staticmethod
    def get_by_id(target_id, env=None):
        url = f"{ExternalApiConfig.get_external_api_user_management_url(env)}/api/v1/Customer/by-odooId/{target_id}"


        try:
            response = requests.get(url, headers=ExternalAuthUtil.get_auth_headers(env), verify=False)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as err:
            raise UserError(
                f"Error Fetching customers from User-Managment: {json.loads(err.response.content.decode('utf-8'))}")

    @staticmethod
    def create(target_data, env=None):
        url = f"{ExternalApiConfig.get_external_api_user_management_url(env)}/api/v1/Customer/create/by-odooId"
        response = requests.post(url, json=target_data, headers=ExternalAuthUtil.get_auth_headers(env), verify=False)

        try:
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as err:
            raise UserError(f"Error creating customer to User-Managment: {json.loads(err.response.content.decode('utf-8'))}")

    @staticmethod
    def update(target_id, target_data, env=None):
        url = f"{ExternalApiConfig.get_external_api_user_management_url(env)}/api/v1/Customer/update/by-odooId?OdooId={target_id}"
        response = requests.put(url, json=target_data, headers=ExternalAuthUtil.get_auth_headers(env), verify=False)
        try:
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as err:
            raise UserError(f"Error updating customer to User-Managment: {json.loads(err.response.content.decode('utf-8'))}")

    @staticmethod
    def delete(target_id, env=None):
        url = f"{ExternalApiConfig.get_external_api_user_management_url(env)}/api/v1/Customer/delete/by-odooId/{target_id}"

        response = requests.delete(url, headers=ExternalAuthUtil.get_auth_headers(env), verify=False)

        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as err:
            raise UserError(f"Error deleting customer from User-Managment: {json.loads(err.response.content.decode('utf-8'))}")
