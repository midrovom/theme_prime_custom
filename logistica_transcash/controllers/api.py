"""Endpoint de ingreso idempotente del ERP. Token de integración independiente.
No utiliza auth='none' ni CORS; acceso exclusivamente por HTTPS detrás de proxy.
"""
import hmac

from odoo import http
from odoo.exceptions import ValidationError
from odoo.http import request


class TranscashIntegrationAPI(http.Controller):
    @http.route('/api/transcash/v1/guias', type='http', auth='public',
                methods=['POST'], csrf=False, save_session=False)
    def receive_guides(self, **kwargs):
        cfg = request.env['ir.config_parameter'].sudo()
        expected = cfg.get_param('logistica_transcash.api_inbound_token') or ''
        supplied = request.httprequest.headers.get('Authorization', '')
        if not expected or not supplied.startswith('Bearer ') or not hmac.compare_digest(
                expected.encode(), supplied[7:].encode()):
            return request.make_json_response({'error': 'No autorizado'}, status=401)
        raw = request.httprequest.get_data(cache=True)
        if len(raw) > 2 * 1024 * 1024:
            return request.make_json_response({'error': 'Petición demasiado grande'}, status=413)
        if not request.httprequest.is_json:
            return request.make_json_response({'error': 'Se requiere application/json'}, status=415)
        try:
            data = request.httprequest.get_json(silent=False)
            outcome = request.env['transcash.guia'].sudo().sync_payload(data)
            return request.make_json_response(outcome, status=207 if outcome['errores'] else 200)
        except (ValueError, ValidationError, TypeError) as err:
            return request.make_json_response({'error': str(err)[:300]}, status=400)
