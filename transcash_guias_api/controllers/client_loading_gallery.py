# -*- coding: utf-8 -*-
"""Evidencia de carga del cliente con aislamiento por guía y destinatario.

Nunca se comparte una foto/video de una ruta que agrupe destinatarios distintos.
"""
import base64
import re
from werkzeug.utils import secure_filename

from odoo import http
from odoo.http import request

IMAGE = ('image/jpeg', 'image/png', 'image/webp', 'image/heic', 'image/heif')
VIDEO = ('video/mp4', 'video/webm', 'video/quicktime')


class ClientTransportLoadingGallery(http.Controller):
    def _authorized_guide(self, guide_id):
        user = request.env.user
        if not user.share or not user.has_group('logistica_transcash.group_transcash_cliente'):
            return False
        g = request.env['transcash.guia'].sudo().browse(guide_id).exists()
        if not g or not g.embarque_id or g.embarque_id.modalidad_transporte != 'cliente' or not g._is_recipient(user):
            return False
        allowed = request.env['transcash.acceso.cliente']._allowed_companies_for(user)
        if allowed is not None and g.company_id.id not in allowed:
            return False
        return g

    @staticmethod
    def _share_route_for_guide(g):
        route = g.hoja_ruta_id
        if not route or route.embarque_id != g.embarque_id or not route.guia_ids:
            return False
        owner = g.destinatario_id.commercial_partner_id
        # No divulgar contenido compartido de una ruta a destinatarios distintos.
        return route if owner and all(item.destinatario_id.commercial_partner_id == owner
                                     for item in route.guia_ids) else False

    @http.route('/transcash/cliente/guias/<int:guide_id>/carga', type='http', auth='user', website=True, methods=['GET'])
    def loading_gallery(self, guide_id, **kw):
        guia = self._authorized_guide(guide_id)
        if not guia:
            return request.not_found()
        route = self._share_route_for_guide(guia)
        route_files = route.evidencia_carga_ids.filtered(lambda e: e.mime in IMAGE + VIDEO) if route else []
        own_files = guia.evidencia_ids.filtered(lambda e: e.tipo == 'carga' and e.archivo and
                                               e.archivo_mime in IMAGE + VIDEO)
        response = request.render('transcash_guias_api.tc_cliente_carga_segura_v226', {
            'guia': guia, 'route_files': route_files, 'own_files': own_files,
            'has_legacy_video': bool(route and route.video_carga and route.video_mime in VIDEO),
            'safe_route': bool(route),
        })
        response.headers['Cache-Control'] = 'private, no-store'
        return response

    @staticmethod
    def _response_for(blob, mime, filename, is_video=False):
        data = base64.b64decode(blob)
        headers = [
            ('Content-Type', mime), ('X-Content-Type-Options', 'nosniff'),
            ('Cache-Control', 'private, no-store'),
            ('Content-Disposition', 'inline; filename="%s"' % (secure_filename(filename or 'evidencia') or 'evidencia')),
            ('Accept-Ranges', 'bytes'),
        ]
        header = request.httprequest.headers.get('Range', '').strip()
        if header and is_video:
            match = re.fullmatch(r'bytes=(\d*)-(\d*)', header)
            if not match or not any(match.groups()):
                return request.make_response(b'', headers=headers + [('Content-Range', 'bytes */%d' % len(data))], status=416)
            left, right = match.groups()
            start = int(left) if left else max(0, len(data) - int(right))
            end = min(int(right), len(data) - 1) if right else len(data) - 1
            if start > end or start >= len(data):
                return request.make_response(b'', headers=headers + [('Content-Range', 'bytes */%d' % len(data))], status=416)
            return request.make_response(data[start:end+1], headers=headers + [
                ('Content-Range', 'bytes %d-%d/%d' % (start, end, len(data))),
                ('Content-Length', str(end-start+1)),
            ], status=206)
        return request.make_response(data, headers=headers + [('Content-Length', str(len(data)))])

    @http.route('/transcash/cliente/guias/<int:guide_id>/carga/ruta/<int:evidence_id>',
                type='http', auth='user', website=True, methods=['GET'])
    def route_file(self, guide_id, evidence_id, **kw):
        guide = self._authorized_guide(guide_id)
        route = self._share_route_for_guide(guide) if guide else False
        evidence = request.env['transcash.carga.evidencia.ruta'].sudo().browse(evidence_id).exists()
        if not route or not evidence or evidence.ruta_id != route or not evidence.archivo or evidence.mime not in IMAGE + VIDEO:
            return request.not_found()
        return self._response_for(evidence.archivo, evidence.mime, evidence.nombre, evidence.mime in VIDEO)

    @http.route('/transcash/cliente/guias/<int:guide_id>/carga/video',
                type='http', auth='user', website=True, methods=['GET'])
    def legacy_route_video(self, guide_id, **kw):
        guide = self._authorized_guide(guide_id)
        route = self._share_route_for_guide(guide) if guide else False
        if not route or not route.video_carga or route.video_mime not in VIDEO:
            return request.not_found()
        return self._response_for(route.video_carga, route.video_mime, route.video_nombre or 'carga.mp4', True)
