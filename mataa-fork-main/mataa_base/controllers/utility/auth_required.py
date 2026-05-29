from functools import wraps
import jwt
from odoo.http import request
from ..common.BaseApiResponse import BaseApiResponse
from ..constants.jwt_constants import SECRET_KEY


def auth_required(func):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        auth_header = request.httprequest.headers.get('Authorization')
        if not auth_header:
            return BaseApiResponse.unauthorized('Token is missing')

        try:
            token = auth_header.split(' ')[1]  # Assume the format is "Bearer <token>"
            payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
            request.env.context = dict(request.env.context, user_id=payload['user_id'])
        except jwt.ExpiredSignatureError:
            return BaseApiResponse.unauthorized('Token has expired')
        except jwt.InvalidTokenError:
            return BaseApiResponse.unauthorized('Invalid token')

        return func(self, *args, **kwargs)

    return wrapper