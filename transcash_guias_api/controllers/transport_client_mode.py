# -*- coding: utf-8 -*-
"""PWA: selección de modalidad y cierre interno de transporte enviado por cliente."""
from urllib.parse import quote

from odoo import http, _
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.http import request
from .route_pwa_speed_sync import TranscashOperacionRapida
from odoo.addons.logistica_transcash.controllers.embarque import EmbarquePortal


class TranscashOperacionModalidad(TranscashOperacionRapida):
    # En v5.32 estas operaciones POST llegan directamente al controlador base.
    # Mantener sus validaciones y endpoints; solo diferir los avisos automáticos
    # de la bitácora Odoo, que de otro modo dependen de un remitente de correo.
    @http.route()
    def route_media(self, route_id, **post):
        request.update_context(mail_notify_force_send=False, tc_pwa_audit_note=True)
        return super().route_media(route_id, **post)

    @http.route()
    def trip_release(self, trip_id, **post):
        request.update_context(mail_notify_force_send=False, tc_pwa_audit_note=True)
        return super().trip_release(trip_id, **post)

    @http.route()
    def trip_resolve(self, trip_id, **post):
        request.update_context(mail_notify_force_send=False, tc_pwa_audit_note=True)
        return super().trip_resolve(trip_id, **post)

    @http.route()
    def trip_reopen(self, trip_id, **post):
        request.update_context(mail_notify_force_send=False, tc_pwa_audit_note=True)
        return super().trip_reopen(trip_id, **post)

    @http.route()
    def route_confirm(self, route_id, **post):
        request.update_context(mail_notify_force_send=False, tc_pwa_audit_note=True)
        return super().route_confirm(route_id, **post)

    @http.route()
    def trip_new(self, **post):
        if request.httprequest.method == 'POST':
            modalidad = (post.get('modalidad_transporte') or 'contratado').strip()
            if modalidad not in ('contratado', 'cliente'):
                return request.redirect('/transcash/operacion/embarques/nuevo?error=Modalidad+inv%C3%A1lida')
            if not self._guard():
                return request.not_found()
            # Solo el POST autenticado de esta pantalla puede definir la
            # modalidad inicial; no depender de un valor libre dentro del wizard.
            request.update_context(tc_modalidad_transport_request=modalidad)
        return super().trip_new(**post)

    @http.route('/transcash/operacion/embarques/<int:trip_id>/cliente-entregado',
                type='http', auth='user', website=True, methods=['POST'], csrf=True)
    def client_delivery_done(self, trip_id, **post):
        if not self._guard():
            return request.not_found()
        trip = self._trip(trip_id)
        if not trip:
            return request.not_found()
        try:
            trip.action_close_client_delivery(post.get('constancia') or '')
            return request.redirect('/transcash/operacion/embarques/%d?ok=entregado' % trip.id)
        except (UserError, AccessError, ValidationError, ValueError) as err:
            return request.redirect('/transcash/operacion/embarques/%d?error=%s' %
                                    (trip.id, quote(str(err)[:350])))

    @http.route('/transcash/operacion/embarques/<int:trip_id>/cliente-marcar',
                type='http', auth='user', website=True, methods=['POST'], csrf=True)
    def set_client_mode(self, trip_id, **post):
        if not self._guard():
            return request.not_found()
        trip = self._trip(trip_id)
        if not trip:
            return request.not_found()
        try:
            trip.action_set_client_transport()
            return request.redirect('/transcash/operacion/embarques/%d?ok=modalidad' % trip.id)
        except (UserError, AccessError, ValidationError) as err:
            return request.redirect('/transcash/operacion/embarques/%d?error=%s' %
                                    (trip.id, quote(str(err)[:350])))

    @http.route('/transcash/operacion/embarques/<int:trip_id>/contratado-marcar',
                type='http', auth='user', website=True, methods=['POST'], csrf=True)
    def set_contracted_mode(self, trip_id, **post):
        if not self._guard():
            return request.not_found()
        trip = self._trip(trip_id)
        if not trip:
            return request.not_found()
        try:
            trip.action_set_contracted_transport()
            return request.redirect('/transcash/operacion/embarques/%d?ok=modalidad' % trip.id)
        except (UserError, AccessError, ValidationError) as err:
            return request.redirect('/transcash/operacion/embarques/%d?error=%s' %
                                    (trip.id, quote(str(err)[:350])))


class EmbarquePortalModalidad(EmbarquePortal):
    def _can_see_embark(self, rec):
        if rec and rec.modalidad_transporte == 'cliente' and request.env.user.share:
            # El proveedor y el chofer no participan en esta modalidad.
            return False
        return super()._can_see_embark(rec)

from odoo.addons.logistica_transcash.controllers.portal import TranscashPortal


class TranscashGuiasPortalModalidad(TranscashPortal):
    def _visible_domain(self):
        domain = super()._visible_domain()
        user = request.env.user
        if user.share and not user.has_group('logistica_transcash.group_transcash_cliente') and (
                user.has_group('logistica_transcash.group_transcash_chofer') or
                user.has_group('logistica_transcash.group_transcash_transportista')):
            return domain + [('embarque_id.modalidad_transporte', '!=', 'cliente')]
        return domain

    def _guide(self, guide_id):
        guide = super()._guide(guide_id)
        user = request.env.user
        if guide and guide.embarque_id.modalidad_transporte == 'cliente' and user.share and not user.has_group(
                'logistica_transcash.group_transcash_cliente'):
            return False
        return guide
