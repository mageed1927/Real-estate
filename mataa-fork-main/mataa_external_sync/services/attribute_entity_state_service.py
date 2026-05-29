# services/attribute_entity_state_sync_service.py
import json
import requests
from odoo.exceptions import UserError
from ..constants.external_api_config import ExternalApiConfig
from ..utilities.external_auth import ExternalAuthUtil


class AttributeEntityStateSyncService:

    @staticmethod
    def map_visibility_to_state(visibility):
        return 1 if str(visibility).lower() == 'visible' else 2

    @staticmethod
    def update_state_by_odoo_id(odoo_name, visibility):
        if not odoo_name:
            raise UserError("Missing odoo_id for attribute entity-state update.")

        entity_state = AttributeEntityStateSyncService.map_visibility_to_state(visibility)
        base = ExternalApiConfig.get_external_api_catalog_management_url()
        url = f"{base}/api/v1/Attributes/UpdateAttributeEntityState/{odoo_name}"

        payload = {"entityState": entity_state}
        headers = ExternalAuthUtil.get_auth_headers()

        resp = requests.put(url, json=payload, headers=headers, verify=False)
        try:
            resp.raise_for_status()
        except requests.exceptions.HTTPError as err:
            try:
                ext_msg = json.loads(err.response.content.decode("utf-8"))
            except Exception:
                ext_msg = err.response.text if err.response is not None else str(err)
            raise UserError(f"Error updating attribute entity-state to Product-Catalog: {ext_msg}")
