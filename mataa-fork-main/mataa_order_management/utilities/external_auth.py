from ..constants.external_api_config import ExternalApiConfig


class ExternalAuthUtil:
    @staticmethod
    def get_dtrack_auth_headers():
        api_key = ExternalApiConfig.get_api_key()
        headers = {
            "Content-Type": "application/json",
            "X-API-KEY": api_key
        }

        return headers

    @staticmethod
    def get_vdm_auth_headers():
        headers = {
            "Content-Type": "application/json",
        }

        return headers


    @staticmethod
    def get_mataa_wallet_auth_headers():
        headers = {
            'accept': '*/*',
            'Content-Type': 'application/json'
        }
        return headers
