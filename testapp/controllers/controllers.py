# -*- coding: utf-8 -*-
# from odoo import http


# class Testapp(http.Controller):
#     @http.route('/testapp/testapp', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/testapp/testapp/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('testapp.listing', {
#             'root': '/testapp/testapp',
#             'objects': http.request.env['testapp.testapp'].search([]),
#         })

#     @http.route('/testapp/testapp/objects/<model("testapp.testapp"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('testapp.object', {
#             'object': obj
#         })

