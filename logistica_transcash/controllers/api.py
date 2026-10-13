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
        if len(raw) > 5 * 1024 * 1024:
            return request.make_json_response({'error': 'Petición demasiado grande'}, status=413)
        if not request.httprequest.is_json:
            return request.make_json_response({'error': 'Se requiere application/json'}, status=415)
        try:
            data = request.httprequest.get_json(silent=False)
            outcome = request.env['transcash.guia'].sudo().sync_payload(data)
            return request.make_json_response(outcome, status=207 if outcome['errores'] else 200)
        except (ValueError, ValidationError, TypeError) as err:
            return request.make_json_response({'error': str(err)[:300]}, status=400)

    @http.route('/api/transcash/v1/notas-credito/estado', type='http', auth='public',
                methods=['POST'], csrf=False, save_session=False)
    def credit_note_status(self, **kwargs):
        """Confirmación desde ERP después de emisión fiscal (o rechazo)."""
        cfg = request.env['ir.config_parameter'].sudo()
        expected = cfg.get_param('logistica_transcash.api_inbound_token') or ''
        supplied = request.httprequest.headers.get('Authorization', '')
        if not expected or not supplied.startswith('Bearer ') or not hmac.compare_digest(
                expected.encode(), supplied[7:].encode()):
            return request.make_json_response({'error':'No autorizado'}, status=401)
        raw = request.httprequest.get_data(cache=True)
        if len(raw) > 16384:
            return request.make_json_response({'error':'Carga demasiado grande'}, status=413)
        if not request.httprequest.is_json:
            return request.make_json_response({'error':'Se requiere JSON'}, status=415)
        try:
            data = request.httprequest.get_json(silent=False)
            result = request.env['transcash.nota.credito'].sudo().with_context(
                transcash_erp_callback=True).confirm_from_erp(data)
            return request.make_json_response(result)
        except (ValueError, TypeError, ValidationError) as err:
            return request.make_json_response({'error':str(err)[:300]}, status=400)

    @http.route('/api/transcash/v1/evidencias/<int:evidence_id>/archivo',
                type='http', auth='public', methods=['GET'], csrf=False, save_session=False)
    def erp_evidence_file(self, evidence_id, **kwargs):
        """Fotos/videos de roturas aprobadas: API privada, nunca URLs públicas."""
        cfg = request.env['ir.config_parameter'].sudo()
        expected = cfg.get_param('logistica_transcash.api_inbound_token') or ''
        supplied = request.httprequest.headers.get('Authorization', '')
        if not expected or not supplied.startswith('Bearer ') or not hmac.compare_digest(
                expected.encode(), supplied[7:].encode()):
            return request.make_json_response({'error':'No autorizado'}, status=401)
        evidence = request.env['transcash.evidencia'].sudo().browse(evidence_id).exists()
        if not evidence or not evidence.archivo or not evidence.rotura_id or evidence.rotura_id.estado != 'aprobada':
            return request.not_found()
        allowed = ('image/jpeg','image/png','image/webp','image/heic','image/heif',
                   'video/mp4','video/quicktime','video/webm','video/3gpp')
        if evidence.archivo_mime not in allowed:
            return request.not_found()
        import base64
        from werkzeug.utils import secure_filename
        filename = secure_filename(evidence.archivo_nombre or 'evidencia')
        return request.make_response(base64.b64decode(evidence.archivo), headers=[
            ('Content-Type', evidence.archivo_mime),
            ('Content-Disposition','attachment; filename="%s"' % filename),
            ('X-Content-Type-Options','nosniff'), ('Cache-Control','private, no-store'),
        ])
