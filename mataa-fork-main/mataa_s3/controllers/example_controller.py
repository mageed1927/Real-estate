# from odoo import http
# from odoo.http import request
# import json
# from odoo.addons.mataa_base.controllers.common.BaseApiResponse import BaseApiResponse
# from odoo.addons.mataa_base.controllers.utility.auth_required import auth_required
#
#
# class ExampleController(http.Controller):
#     @http.route('/api/example', type='http', auth='public', methods=['GET'], csrf=False)
#     def get_examples(self, page=1, page_size=10):
#         page = int(page)
#         page_size = int(page_size)
#         offset = (page - 1) * page_size
#         limit = page_size
#         examples = request.env['mataa.s3.example'].sudo().search([], limit=limit, offset=offset)
#         total_count = request.env['mataa.s3.example'].sudo().search_count([])
#         examples_data = examples.read(['id', 'name', 'value', 'value2', 'description'])
#         meta = {
#             'total_count': total_count,
#             'page': page,
#             'page_size': page_size,
#             'total_pages': (total_count + page_size - 1) // page_size
#         }
#         return BaseApiResponse.success(data=examples_data, meta=meta)
#
#     @http.route('/api/example/<int:example_id>', type='http', auth='public', methods=['GET'], csrf=False)
#     def get_example(self, example_id):
#         example = request.env['mataa.s3.example'].sudo().browse(example_id)
#         if not example.exists():
#             return BaseApiResponse.not_found()
#         example_data = example.read(['id', 'name', 'value', 'value2', 'description'])[0]
#         return BaseApiResponse.success(data=example_data)
#
#     @auth_required
#     @http.route('/api/example', type='http', auth='public', methods=['POST'], csrf=False)
#     def create_example(self):
#         data = json.loads(request.httprequest.data)
#         new_example = request.env['mataa.s3.example'].sudo().create({
#             'name': data.get('name'),
#             'value': data.get('value'),
#             'description': data.get('description', ''),
#         })
#         new_example_data = new_example.read(['id', 'name', 'value', 'value2', 'description'])[0]
#         return BaseApiResponse.created(data=new_example_data, message='Example created successfully')
#
#     @http.route('/api/example/<int:example_id>', type='http', auth='public', methods=['PUT'], csrf=False)
#     def update_example(self, example_id):
#         data = json.loads(request.httprequest.data)
#         example = request.env['mataa.s3.example'].sudo().browse(example_id)
#         if not example.exists():
#             return BaseApiResponse.not_found()
#         example.write({
#             'name': data.get('name'),
#             'value': data.get('value'),
#             'description': data.get('description', ''),
#         })
#         updated_example_data = example.read(['id', 'name', 'value', 'value2', 'description'])[0]
#         return BaseApiResponse.success(data=updated_example_data, message='Example updated successfully')
#
#     @http.route('/api/example/<int:example_id>', type='http', auth='public', methods=['DELETE'], csrf=False)
#     def delete_example(self, example_id):
#         example = request.env['mataa.s3.example'].sudo().browse(example_id)
#         if not example.exists():
#             return BaseApiResponse.not_found()
#         example.unlink()
#         return BaseApiResponse.no_content(message='Example deleted successfully')
