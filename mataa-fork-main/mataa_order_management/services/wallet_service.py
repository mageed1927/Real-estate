# -*- coding: utf-8 -*-

import requests

from odoo.exceptions import UserError
from ..constants.external_api_config import ExternalApiConfig
from ..utilities.external_auth import ExternalAuthUtil


class WalletService:
    @staticmethod
    def initiate_deposit(target_data):
        url = f"{ExternalApiConfig.get_wallet_api_url()}/InitiateDeposit"

        response = requests.post(url, json=target_data, headers=ExternalAuthUtil.get_mataa_wallet_auth_headers(), verify=False)

        try:
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise UserError(f"Error creating deposit: {e}\nResponse: {response.text}")

    @staticmethod
    def add_deduction(target_data):
        url = f"{ExternalApiConfig.get_wallet_api_url()}/Deduction"

        response = requests.post(url, json=target_data, headers=ExternalAuthUtil.get_mataa_wallet_auth_headers(), verify=False)

        try:
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise UserError(f"Error creating deduction: {e}\nResponse: {response.text}")

    @staticmethod
    def set_on_hold(transaction_odoo_id):
        url = f"{ExternalApiConfig.get_transaction_api_url()}/SetOnhold"

        data = {"transactionOdooId": f"{transaction_odoo_id}"}

        response = requests.post(url, json=data, headers=ExternalAuthUtil.get_mataa_wallet_auth_headers(), verify=False)
        try:
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise UserError(f"Error setting transaction on hold: {e}\nResponse: {response.text}")

    @staticmethod
    def reset_on_hold(transaction_odoo_id):
        url = f"{ExternalApiConfig.get_transaction_api_url()}/ResetOnhold"

        data = {"transactionOdooId": f"{transaction_odoo_id}"}

        response = requests.post(url, json=data, headers=ExternalAuthUtil.get_mataa_wallet_auth_headers(), verify=False)

        try:
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise UserError(f"Error resetting transaction on hold: {e}\nResponse: {response.text}")