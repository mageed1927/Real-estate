# controllers/import_api_controller.py
import json
from odoo import http
from odoo.http import request
from odoo.exceptions import UserError
from ..services.import_api_service import ImportApiService

class ImportApiController(http.Controller):

    @http.route('/api/product/import', type='http', auth='none', csrf=False, methods=['POST'])
    def import_single(self):
        try:
            raw_data = request.httprequest.data
            payload = json.loads(raw_data.decode('utf-8')) if raw_data else {}

            behaviour = payload.get('behaviour', 'create_update')
            row = payload.get('row') or {}

            result = ImportApiService.process_row(request.env, row, behaviour)
            return request.make_json_response({
                "ok": True,
                "result": result
            })

        except UserError as ue:
            return request.make_json_response({
                "ok": False,
                "error": str(ue)
            }, status=400)

        except Exception as e:
            request.env.cr.rollback()
            return request.make_json_response({
                "ok": False,
                "error": f"Unexpected error: {str(e)}"
            }, status=500)


    @http.route('/api/product/import/bulk', type='http', auth='none', csrf=False, methods=['POST'])
    def import_bulk(self):
        try:
            raw_data = request.httprequest.data
            payload = json.loads(raw_data.decode('utf-8')) if raw_data else {}

            behaviour = payload.get('behaviour', 'create_update')
            rows = payload.get('rows') or []

            successes = []
            failures = []

            for idx, row in enumerate(rows, start=1):
                try:
                    res = ImportApiService.process_row(request.env, row, behaviour=behaviour)
                    if isinstance(res, dict):
                        successes.append({"index": idx, **res})
                    else:
                        raise UserError(f"Invalid response from process_row: {res}")
                except Exception as e:
                    failures.append({
                        "index": idx,
                        "row": row,
                        "error": str(e)
                    })

            response = {
                "ok": len(failures) == 0,
                "success_count": len(successes),
                "failure_count": len(failures),
                "successes": successes,
                "failures": failures
            }

            return request.make_json_response(response)

        except Exception as e:
            return request.make_json_response({
                "ok": False,
                "error": str(e)
            }, status=500)