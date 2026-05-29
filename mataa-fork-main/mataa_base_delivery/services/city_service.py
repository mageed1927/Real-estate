import requests
from odoo import api, SUPERUSER_ID


class CityService:
    @staticmethod
    def send_area_update(env, area, vals=None):
        try:
            base_url = env['ir.config_parameter'].sudo().get_param('mataa_external_sync.external_api_base_url') + "/OrderManagement"
            url = f"{base_url}/api/v1/Area/OdooId/{area.id}"
            delivery_cost = CityService._get_delivery_cost(area, vals)

            data = {
                "name": area.name,
                "areaCode": area.code,
                "deliveryCost": delivery_cost,
            }

            response = requests.put(url, json=data, timeout=30)
            response.raise_for_status()

        except requests.exceptions.RequestException as e:
            raise Exception(f"API request failed: {str(e)}")
        except Exception as e:
            raise Exception(f"Unexpected error in area update: {str(e)}")

    @staticmethod
    def _get_delivery_cost(area, vals=None):
        if vals:
            if 'camex_total_cost' in vals:
                return vals['camex_total_cost']
            elif 'line_total_cost' in vals:
                return vals['line_total_cost']

        if hasattr(area, 'camex_total_cost') and area.camex_total_cost:
            return area.camex_total_cost
        elif hasattr(area, 'line_total_cost') and area.line_total_cost:
            return area.line_total_cost

        return 0.0