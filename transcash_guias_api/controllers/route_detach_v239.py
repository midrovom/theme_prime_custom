# -*- coding: utf-8 -*-
"""Acción móvil para retirar una ruta sin perder su expediente."""
from urllib.parse import quote

from odoo import http, _
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.http import request

from .route_reopen_edit_v238 import TranscashEditExistingRouteV238


class TranscashRouteDetachV239(TranscashEditExistingRouteV238):
    @http.route('/transcash/operacion/embarques/<int:trip_id>/rutas/quitar',
                type='http', auth='user', website=True, methods=['POST'], csrf=True)
    def tc_trip_detach_route(self, trip_id, **post):
        if not self._guard():
            return request.not_found()
        trip = self._trip(trip_id)
        if not trip:
            return request.not_found()
        try:
            route_id = self._tc_safe_id(post.get('ruta_id'))
            if not route_id:
                raise UserError(_('Seleccione la hoja de ruta que desea quitar.'))
            with request.env.cr.savepoint():
                trip.action_tc_detach_route(route_id)
            return request.redirect('/transcash/operacion/embarques/%d?ok=ruta-retirada' % trip.id)
        except (UserError, AccessError, ValidationError) as exc:
            return request.redirect('/transcash/operacion/embarques/%d?error=%s' % (
                trip.id, quote(str(exc)[:320])))
