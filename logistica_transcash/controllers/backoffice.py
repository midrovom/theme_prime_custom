"""Galería privada de backoffice; no expone otras guías ni media sin autorización."""
from odoo import http
from odoo.http import request
from odoo.exceptions import AccessError


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
