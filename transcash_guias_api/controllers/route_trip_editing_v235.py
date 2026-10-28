# -*- coding: utf-8 -*-
"""Acciones PWA para reorganizar rutas y viajes antes de aceptación."""
from urllib.parse import quote
from odoo import http, _
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.http import request

from .transport_client_mode import TranscashOperacionModalidad


class TranscashEditarPlanificacion(TranscashOperacionModalidad):
    def _page(self, heading, **values):
        values.setdefault('tc_viaje_retorno', False)
        values.setdefault('tc_rutas_compatibles', request.env['transcash.hoja.ruta'])
        return super()._page(heading, **values)

    def _tc_trip_options(self, trip):
        return request.env['transcash.hoja.ruta'].search([
            ('company_id', '=', trip.company_id.id),
            ('embarque_id', '=', False),
            ('state', 'in', ('planificada', 'cargada')),
            ('chofer_usuario_id', '=', trip.chofer_usuario_id.id),
            ('proveedor_id', '=', trip.proveedor_id.id),
            ('tipo_vehiculo', '=', trip.tipo_vehiculo),
            ('placa', '=ilike', (trip.placa or '').strip()),
        ], order='id desc', limit=150).filtered(
            lambda r: (r.placa or '').strip().upper() == (trip.placa or '').strip().upper())

    @http.route()
    def trip_detail(self, trip_id, **kw):
        if not self._guard():
            return request.not_found()
        trip = self._trip(trip_id)
        if not trip:
            return request.not_found()
        response = self._page('Embarque ' + trip.name, section='embarque_detalle',
                              embarque=trip, can_approve_freight=self._manager(),
                              error=kw.get('error'), ok=kw.get('ok'),
                              tc_rutas_compatibles=(self._tc_trip_options(trip)
                                                   if trip.state == 'preparacion' else
                                                   request.env['transcash.hoja.ruta']),
                              **self._tc_gallery_for_trip(trip))
        return response

    def _tc_gallery_for_trip(self, trip):
        from logistica_transcash.controllers.evidence_hub import gallery_for_trip
        return gallery_for_trip(trip)

    @http.route()
    def route_new(self, **post):
        # Mantener la validación optimizada de v2.23. Solo precargar los filtros
        # del viaje y recordar a qué viaje debe volver el operador.
        trip_id = self._tc_safe_id(post.get('embarque_id'))
        trip = self._trip(trip_id) if trip_id and self._guard() else False
        if trip and trip.state != 'preparacion':
            trip = False
        if request.httprequest.method == 'GET' and trip:
            form = {
                'chofer_id': str(trip.chofer_usuario_id.id),
                'proveedor_id': str(trip.proveedor_id.id),
                'placa': trip.placa or '',
                'tipo_vehiculo': trip.tipo_vehiculo or '',
                'origen': trip.origen or '',
            }
            return self._page('Nueva hoja de ruta', section='nueva', form_values=form,
                              tc_viaje_retorno=trip, **self._new_options())
        response = super().route_new(**post)
        if request.httprequest.method == 'POST' and trip:
            location = response.headers.get('Location', '')
            if '/transcash/operacion/rutas/' in location and '?ok=creada' in location:
                response.headers['Location'] = location + '&embarque_id=%s' % trip.id
        return response

    def _tc_valid_return_trip(self, route_id, post):
        trip_id = self._tc_safe_id(post.get('tc_viaje_regreso'))
        trip = self._trip(trip_id) if trip_id else False
        route = self._route(route_id) if trip else False
        return trip if (route and trip and trip.state == 'preparacion' and
                        route.company_id == trip.company_id and
                        route.chofer_usuario_id == trip.chofer_usuario_id and
                        route.proveedor_id == trip.proveedor_id and
                        route.tipo_vehiculo == trip.tipo_vehiculo and
                        (route.placa or '').strip().upper() == (trip.placa or '').strip().upper()) else False

    @http.route()
    def route_select(self, route_id, **post):
        trip = self._tc_valid_return_trip(route_id, post) if self._guard() else False
        response = super().route_select(route_id, **post)
        if trip and '/transcash/operacion/rutas/%d?' % route_id in response.headers.get('Location', ''):
            response.headers['Location'] += '&embarque_id=%s' % trip.id
        return response

    @http.route()
    def route_confirm(self, route_id, **post):
        trip = self._tc_valid_return_trip(route_id, post) if self._guard() else False
        response = super().route_confirm(route_id, **post)
        if trip and '/transcash/operacion/rutas/%d?' % route_id in response.headers.get('Location', ''):
            response.headers['Location'] += '&embarque_id=%s' % trip.id
        return response

    @staticmethod
    def _tc_safe_id(value):
        try:
            return int(value or 0)
        except (ValueError, TypeError):
            return 0

    @http.route('/transcash/operacion/rutas/<int:route_id>/eliminar', type='http',
                auth='user', website=True, methods=['POST'], csrf=True)
    def tc_route_delete(self, route_id, **post):
        if not self._guard():
            return request.not_found()
        route = self._route(route_id)
        if not route:
            return request.not_found()
        try:
            with request.env.cr.savepoint():
                route.action_tc_delete_unassigned_route()
            return request.redirect('/transcash/operacion/rutas?ok=eliminada')
        except (UserError, AccessError, ValidationError) as exc:
            return request.redirect('/transcash/operacion/rutas/%d?error=%s' % (
                route.id, quote(str(exc)[:320])))

    @http.route('/transcash/operacion/embarques/<int:trip_id>/eliminar', type='http',
                auth='user', website=True, methods=['POST'], csrf=True)
    def tc_trip_delete(self, trip_id, **post):
        if not self._guard():
            return request.not_found()
        trip = self._trip(trip_id)
        if not trip:
            return request.not_found()
        try:
            with request.env.cr.savepoint():
                trip.action_tc_delete_unaccepted_trip()
            return request.redirect('/transcash/operacion?ok=viaje-eliminado')
        except (UserError, AccessError, ValidationError) as exc:
            return request.redirect('/transcash/operacion/embarques/%d?error=%s' % (
                trip.id, quote(str(exc)[:320])))

    @http.route('/transcash/operacion/embarques/<int:trip_id>/rutas/agregar', type='http',
                auth='user', website=True, methods=['POST'], csrf=True)
    def tc_trip_add_route(self, trip_id, **post):
        if not self._guard():
            return request.not_found()
        trip = self._trip(trip_id)
        if not trip:
            return request.not_found()
        try:
            route_id = self._tc_safe_id(post.get('ruta_id'))
            if not route_id:
                raise UserError(_('Seleccione una hoja de ruta.'))
            trip.env['transcash.hoja.ruta']._check_operator()
            if trip.state != 'preparacion':
                raise UserError(_('Solo se agregan rutas a viajes en preparación.'))
            route = self._tc_trip_options(trip).filtered(lambda r: r.id == route_id)
            if not route:
                raise UserError(_('La ruta ya no está disponible o corresponde a otro transporte.'))
            with request.env.cr.savepoint():
                wizard = request.env['transcash.armar.embarque.wizard'].create({
                    'ruta_ids': [(6, 0, [route.id])],
                    'embarque_id': trip.id,
                    'company_id': trip.company_id.id,
                    'proveedor_id': trip.proveedor_id.id,
                    'chofer_usuario_id': trip.chofer_usuario_id.id,
                    'tipo_vehiculo': trip.tipo_vehiculo,
                    'placa': trip.placa,
                    'modalidad_transporte': trip.modalidad_transporte,
                })
                wizard.action_confirm()  # validación y bloqueo reales del negocio
            return request.redirect('/transcash/operacion/embarques/%d?ok=ruta-agregada' % trip.id)
        except (UserError, AccessError, ValidationError) as exc:
            return request.redirect('/transcash/operacion/embarques/%d?error=%s' % (
                trip.id, quote(str(exc)[:320])))
