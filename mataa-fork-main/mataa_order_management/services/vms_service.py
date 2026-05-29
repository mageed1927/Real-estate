import requests
from odoo.http import request
from odoo.exceptions import UserError
from ..constants.external_api_config import ExternalApiConfig


def _format_float_to_time_string(time_float):
    """
    Converts a float time (e.g., 8.5) into a formatted time string ('08:30').
    """
    if not isinstance(time_float, (float, int)):
        return ""

    hours = int(time_float)
    minutes = int(round((time_float - hours) * 60))

    return f"{hours:02d}:{minutes:02d}"
class VMSService:

    @staticmethod
    def get_order_line_data(env, order_line_id):
        line = env['purchase.order.line'].sudo().browse(order_line_id)

        product_sorted_images = sorted(line.product_id.image_url_ids, key=lambda img: img.sequence)

        line_data = {
            'line_id': line.id,
            'product_id': line.product_id.id,
            'product_mataa_id': line.product_id.mataa_id,
            'create_date': str(line.create_date),
            'write_date': str(line.write_date),
            'date_order': str(line.date_order) if line.date_order else None,
            'date_approve': str(line.date_approve) if line.date_approve else None,
            'product_name': line.product_id.name,
            'product_sku': line.product_id.default_code or None,
            'product_barcode': line.product_id.barcode or None,
            'product_additional_barcodes': [barcode.name for barcode in line.product_id.barcode_ids] if line.product_id.barcode_ids else [],
            'product_main_image': product_sorted_images[0].url if product_sorted_images else None,
            'product_images_gallery': [image.url for image in product_sorted_images] if product_sorted_images else [],
            'product_attributes': [{
                'attribute_id': attr_value.attribute_id.id,
                'attribute_mataa_id': attr_value.attribute_id.mataa_id,
                'attribute_name': attr_value.attribute_id.name,
                'value_id': attr_value.product_attribute_value_id.id,
                'value_mataa_id': attr_value.product_attribute_value_id.mataa_id,
                'value_name': attr_value.product_attribute_value_id.name
            } for attr_value in line.product_id.product_template_attribute_value_ids] if line.product_id.attribute_line_ids else [],
            'description': line.name,
            'quantity': line.product_qty,
            'available_qty': line.available_qty,
            'unit_price': line.price_unit,
        }
        return line_data

    @staticmethod
    def send_order_to_vms(env, purchase_order,is_updated):

        config = env['ir.config_parameter'].sudo()
        base_url = config.get_param("mataa_order_management.external_vendor_api_url")
        username = config.get_param("mataa_order_management.external_vendor_api_username")
        password = config.get_param("mataa_order_management.external_vendor_api_password")


        auth_url = f"{base_url}/api/auth/Authentication/Login"
        auth_payload = {
            "username": username,
            "password": password
        }
        auth_response = requests.post(auth_url, json=auth_payload, timeout=10)
        auth_response.raise_for_status()
        token = auth_response.json().get("data", {}).get("token")

        if not token:
            raise Exception("Auth token not found in response")

        if not purchase_order and is_updated == True:
            return

        order_lines_payload = []
        for line in purchase_order.order_line:
            line_data = VMSService.get_order_line_data(env, line.id)
            order_lines_payload.append({
                "imageUrl": line_data['product_main_image'],
                "name": line_data['product_name'],
                "code": line_data['product_sku'],
                "barCode": line_data['product_barcode'],
                "quantity": int(line_data['quantity']),
                "ApprovedQuantity": int(line_data['available_qty']) or 0,
                "odooId": line_data['line_id'],
                "unitPrice": line_data['unit_price'],
                "attributes": [
                    {
                        "key": attr['attribute_name'],
                        "value": attr['value_name'],
                        "odooId": attr['value_id']
                    }
                    for attr in line_data['product_attributes']
                ]
            })

        payload = {
            "state": purchase_order.state,
            "vendorOdooId": purchase_order.partner_id.id,
            "code": purchase_order.name,
            "odooId": purchase_order.id,
            "totalPrice": purchase_order.amount_total,
            "blanketCode": purchase_order.requisition_id.name or "",
            "deliverTo": purchase_order.picking_type_id.display_name if purchase_order.picking_type_id else "",
            "orderDetails": order_lines_payload
        }

        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
        try:
            if is_updated:
             url = f'{base_url}/api/v1/Order/detailsFromOdoo/{purchase_order.id}'
             response = requests.put(url, headers=headers, json=payload)
             response.raise_for_status()
            else:
             post_url = f'{base_url}/api/v1/Order/CreateWithDetails/FromOdoo'
             post_response = requests.post(post_url, headers=headers, json=payload)
             post_response.raise_for_status()
        except requests.exceptions.RequestException as e:
         error_message = str(e)
         if hasattr(e, 'response') and e.response is not None:
             try:
                 error_data = e.response.json()
                 error_message = error_data.get('message',error_data.get('error',error_data.get('title', str(e))))
             except (ValueError, AttributeError):
                 error_message = e.response.text or str(e)

         raise UserError(f"Order sync failed: {error_message}")

    @staticmethod
    def create_vendor_in_vms(env,partner,is_updated):
        config = env['ir.config_parameter'].sudo()
        base_url = config.get_param("mataa_order_management.external_vendor_api_url")
        username = config.get_param("mataa_order_management.external_vendor_api_username")
        password = config.get_param("mataa_order_management.external_vendor_api_password")

        try:

            auth_url = f"{base_url}/api/auth/Authentication/Login"
            auth_payload = {
                "username": username,
                "password": password
            }

            auth_response = requests.post(auth_url, json=auth_payload, timeout=10)
            auth_response.raise_for_status()
            token = auth_response.json().get("data", {}).get("token")

            if not token:
                raise Exception("Token not found in authentication response.")

            payload = {
                "name": partner.name or "",
                "phoneNumber": partner.phone or "",
                "vendorState": "Active" if partner.active else "InActive",
                "email": partner.email or "",
                "hasWhatsApp": True,
                "additionalPhoneNumber": partner.mobile or "",
                "mattaId": 0,
                "odooId": partner.id,
                "location": partner.street or "",
                "workingHoursStart": _format_float_to_time_string(partner.working_hours_start),
                "workingHoursEnd": _format_float_to_time_string(partner.working_hours_end)

            }

            headers = {
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json'
            }
            if is_updated:
                url = f"{base_url}/api/v1/Vendor/UpdateFromOdoo/{partner.id}"
                response = requests.put(url, headers=headers, json=payload)
            else:
                url = f"{base_url}/api/v1/Vendor/CreateFromOdoo"
                response = requests.post(url, headers=headers, json=payload)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            error_message = str(e)
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_data = e.response.json()
                    error_message = error_data.get('message',error_data.get('error',error_data.get('title', str(e))))
                except (ValueError, AttributeError):
                    error_message = e.response.text or str(e)
            raise UserError(f"Vendor sync failed: {error_message}")


        except Exception as e:
            raise UserError(f"Unexpected error: {str(e)}")
