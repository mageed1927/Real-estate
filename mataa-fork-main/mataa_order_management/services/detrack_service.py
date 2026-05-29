import requests

from odoo.exceptions import UserError
from ..constants.external_api_config import ExternalApiConfig
from ..utilities.external_auth import ExternalAuthUtil


class DetrackService:
    @staticmethod
    def create_collection_job(target_data):
        url = f"{ExternalApiConfig.get_external_api_base_url()}/api/v2/dn/jobs"

        response = requests.post(url, json=target_data, headers=ExternalAuthUtil.get_dtrack_auth_headers(), verify=False)

        try:
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as err:
            try:
                response_data = response.json()
                error = response_data.get('message')
            except Exception:
                error = "Server returned malformed data (Not JSON)."
            if not error:
                error = response_data.get('errors')
            if not error:
                error = response_data 
            raise UserError(f"Error creating blanket order in dtrack: {error}")
            return None

    @staticmethod
    def update_collection_job(do_number, target_data):
        url = f"{ExternalApiConfig.get_external_api_base_url()}/api/v2/dn/jobs/{do_number}?type=Collection"

        response = requests.put(url, json=target_data, headers=ExternalAuthUtil.get_dtrack_auth_headers(),
                                 verify=False)

        try:
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as err:
            # TODO : handle the error message
            raise UserError(f"Error creating blanket order in dtrack: {err}")
            return None
