from odoo.http import Response
import json


class BaseApiResponse:
    @staticmethod
    def success(data, status=200, message=None, meta=None):
        response_data = {
            'status': 'success',
            'data': data,
            'message': message,
            'meta': meta
        }
        return Response(json.dumps(response_data), content_type='application/json', status=status)

    @staticmethod
    def created(data, message=None):
        return BaseApiResponse.success(data, status=201, message=message)

    @staticmethod
    def deleted(message='Resource deleted successfully'):
        response_data = {
            'status': 'success',
            'message': message
        }
        return Response(json.dumps(response_data), content_type='application/json', status=204)

    @staticmethod
    def no_content(message=None):
        response_data = {
            'status': 'success',
            'message': message
        }
        return Response(json.dumps(response_data), content_type='application/json', status=204)

    @staticmethod
    def error(message, status=400, errors=None):
        response_data = {
            'status': 'error',
            'message': message,
            'errors': errors
        }
        return Response(json.dumps(response_data), content_type='application/json', status=status)

    @staticmethod
    def validation_error(errors, status=422):
        return BaseApiResponse.error(
            message='Validation failed',
            status=status,
            errors=errors
        )

    @staticmethod
    def not_found(message='Resource not found', status=404):
        return BaseApiResponse.error(message=message, status=status)

    @staticmethod
    def unauthorized(message='Unauthorized', status=401):
        return BaseApiResponse.error(message=message, status=status)

    @staticmethod
    def forbidden(message='Forbidden', status=403):
        return BaseApiResponse.error(message=message, status=status)
