"""Galería privada de backoffice; no expone otras guías ni media sin autorización."""
from odoo import http
from odoo.http import request
from odoo.exceptions import AccessError
from .evidence_hub import gallery_for_route


class TranscashBackofficeGallery(http.Controller):
    @http.route('/transcash/backoffice/guias/<int:guide_id>/galeria', type='http',
                auth='user', website=True, methods=['GET'])
    def gallery(self, guide_id, **kwargs):
        guia = request.env['transcash.guia'].sudo().browse(guide_id).exists()
        if not guia:
            return request.not_found()
        try:
            # Important: check in the REAL user environment, not sudo.
            guia.with_user(request.env.user)._check_internal_gallery_access()
        except AccessError:
            return request.not_found()
        allowed_mime = ('image/jpeg', 'image/png', 'image/webp', 'image/heic', 'image/heif',
                        'video/mp4', 'video/webm', 'video/quicktime', 'video/3gpp')
        evidencias = guia.evidencia_ids.filtered(
            lambda ev: ev.archivo_mime in allowed_mime
        ).sorted('create_date', reverse=True)
        response = request.render('logistica_transcash.backoffice_gallery', {
            'guia': guia, 'evidencias': evidencias,
        })
        response.headers['Cache-Control'] = 'private, no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        return response

    @http.route('/transcash/backoffice/rutas/<int:route_id>/galeria', type='http',
                auth='user', website=True, methods=['GET'])
    def route_gallery(self, route_id, **kw):
        user = request.env.user
        ruta = request.env['transcash.hoja.ruta'].sudo().browse(route_id).exists()
        if not ruta or user.share or ruta.company_id not in user.company_ids or not (
            user.has_group('logistica_transcash.group_transcash_consulta') or
            user.has_group('logistica_transcash.group_logistica_bodega') or
            user.has_group('logistica_transcash.group_transcash_operador_rutas') or
            user.has_group('logistica_transcash.group_logistica_manager')
        ):
            return request.not_found()
        response = request.render('logistica_transcash.transcash_evidence_hub_page', {
            'gallery_page_title': ruta.name,
            'gallery_back_url': '/web',
            'embedded': kw.get('embedded') == '1',
            **gallery_for_route(ruta),
        })
        response.headers['Cache-Control'] = 'private, no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        return response
