# -*- coding: utf-8 -*-
"""Acciones PWA de corrección de evidencias, protegidas con CSRF y ORM."""
from urllib.parse import quote

from odoo import http, _
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.http import request

from .route_detach_v239 import TranscashRouteDetachV239


class TranscashEvidenceDeleteV242(TranscashRouteDetachV239):
    @http.route('/transcash/operacion/rutas/<int:route_id>/evidencias/<int:evidence_id>/eliminar',
                type='http', auth='user', website=True, methods=['POST'], csrf=True)
    def tc_delete_loading_evidence(self, route_id, evidence_id, **post):
        if not self._guard():
            return request.not_found()
        route = self._route(route_id)
        if not route:
            return request.not_found()
        back = '/transcash/operacion/embarques/%d' % route.embarque_id.id if route.embarque_id else '/transcash/operacion/rutas/%d' % route.id
        try:
            with request.env.cr.savepoint():
                evidence = request.env['transcash.carga.evidencia.ruta'].browse(evidence_id).exists()
                if not evidence or evidence.ruta_id != route:
                    raise UserError(_('La evidencia ya no existe o no pertenece a esta ruta.'))
                evidence.unlink()
            return request.redirect('%s?ok=evidencia-eliminada#ruta-%d' % (back, route.id))
        except (UserError, AccessError, ValidationError) as exc:
            return request.redirect('%s?error=%s#ruta-%d' % (back, quote(str(exc)[:320]), route.id))

    @http.route('/transcash/operacion/rutas/<int:route_id>/evidencias/video-historico/eliminar',
                type='http', auth='user', website=True, methods=['POST'], csrf=True)
    def tc_delete_legacy_loading_video(self, route_id, **post):
        if not self._guard():
            return request.not_found()
        route = self._route(route_id)
        if not route:
            return request.not_found()
        back = '/transcash/operacion/embarques/%d' % route.embarque_id.id if route.embarque_id else '/transcash/operacion/rutas/%d' % route.id
        try:
            with request.env.cr.savepoint():
                route.action_tc_delete_legacy_loading_video()
            return request.redirect('%s?ok=evidencia-eliminada#ruta-%d' % (back, route.id))
        except (UserError, AccessError, ValidationError) as exc:
            return request.redirect('%s?error=%s#ruta-%d' % (back, quote(str(exc)[:320]), route.id))
