import jwt
import datetime
import json
from odoo import http
from odoo.http import request
from .common.BaseApiResponse import BaseApiResponse
from .constants.jwt_constants import SECRET_KEY


class AuthController(http.Controller):

    @http.route('/api/auth/login', type='http', auth='public', methods=['POST'], csrf=False)
    def login(self):
        data = json.loads(request.httprequest.data)
        username = data.get('username')
        password = data.get('password')

        # user = request.env['res.users'].sudo().search([('login', '=', username), ('password', '=', password)], limit=1)
        user_id = request.session.authenticate(request.session.db, username, password)

        if not user_id:
            return BaseApiResponse.unauthorized('Invalid credentials')

        payload = {
            'user_id': user_id,
            'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=1)  # Token expiration
        }
        token = jwt.encode(payload, SECRET_KEY, algorithm='HS256')

        return BaseApiResponse.success(data={'token': token}, message='Login successful')
