# -*- coding: utf-8 -*-
"""Editor móvil de una ruta libre, reutilizando el formulario de creación."""
from urllib.parse import quote

from odoo import http, _
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.http import request

from .route_trip_editing_v235 import TranscashEditarPlanificacion


class TranscashEditExistingRouteV238(TranscashEditarPlanificacion):
    def _page(self, heading, **values):
        values.setdefault('tc_route_edit', False)
        return super()._page(heading, **values)

    @http.route('/transcash/operacion/rutas/<int:route_id>/editar', type='http',
                auth='user', website=True, methods=['GET', 'POST'], csrf=True)
    def tc_edit_route(self, route_id, **post):
        if not self._guard():
            return request.not_found()
        route = self._route(route_id)
        if not route:
            return request.not_found()
        if request.httprequest.method == 'GET':
            if route.embarque_id or route.state != 'borrador':
                return request.redirect('/transcash/operacion/rutas/%d?error=%s' % (
                    route.id, quote(_('Primero reabra la ruta; las rutas de un viaje no se editan.'))))
            form = dict(chofer_id=str(route.chofer_usuario_id.id),
                        proveedor_id=str(route.proveedor_id.id),
                        destino_id=str(route.destino_id.id),
                        placa=route.placa or '', tipo_vehiculo=route.tipo_vehiculo or '',
                        origen=route.origen or '')
            options = self._new_options()
            # El registro existente debe permanecer visible en los combos, aun
            # cuando haya dejado de aparecer en el catálogo de guías libres.
            for key, item in [('choferes_pwa', route.chofer_usuario_id),
                              ('proveedores_pwa', route.proveedor_id),
                              ('destinos_pwa', route.destino_id)]:
                options[key] |= item
            return self._page('Modificar hoja de ruta ' + route.name,
                              section='nueva', form_values=form, tc_route_edit=route,
                              **options)
        try:
            route._tc_check_reopen_for_edit()
            request.env.cr.execute('SELECT id FROM transcash_hoja_ruta WHERE id=%s FOR UPDATE', (route.id,))
            route.invalidate_recordset(['state', 'embarque_id', 'chofer_usuario_id', 'proveedor_id',
                                        'destino_id', 'seleccion_guia_ids'])
            route._tc_check_reopen_for_edit()
            if route.state != 'borrador':
                raise UserError(_('La ruta ya fue confirmada. Reabra antes de modificar.'))
            try:
                driver_id, provider_id, destination_id = (
                    int(post.get(field) or 0) for field in ('chofer_id', 'proveedor_id', 'destino_id'))
            except (TypeError, ValueError):
                raise ValidationError(_('Selecciona chofer, proveedor y destino válidos.'))
            plate = (post.get('placa') or '').strip().upper()
            vehicle = post.get('tipo_vehiculo')
            if not plate or len(plate) > 20 or vehicle not in ('mula', 'camion', 'camioneta', 'furgon', 'otro'):
                raise ValidationError(_('Comprueba la placa y el tipo de vehículo.'))
            driver = request.env['res.users'].sudo().browse(driver_id).exists()
            provider = request.env['res.partner'].browse(provider_id).exists()
            destination = request.env['transcash.destino'].browse(destination_id).exists()
            driver_group = request.env.ref('logistica_transcash.group_transcash_chofer')
            if not driver or not driver.active or not driver.share or driver_group not in driver.groups_id:
                raise ValidationError(_('El chofer debe ser un usuario Portal activo del perfil chofer.'))
            if not provider or not provider.active or (provider.company_id and provider.company_id != route.company_id):
                raise ValidationError(_('El transportista no está disponible para esta compañía.'))
            if not destination or not destination.active or destination.company_id != route.company_id:
                raise ValidationError(_('El destino no está disponible para esta compañía.'))
            # Mantener las mismas fuentes que el alta original de rutas.
            # La ficha previamente asociada a esta ruta sigue siendo válida
            # aunque ya no figure en los combos de las guías libres.
            if driver_id != route.chofer_usuario_id.id:
                driver_allowed = bool(request.env['transcash.chofer'].sudo().search_count([
                    ('company_id', '=', route.company_id.id), ('activo', '=', True),
                    ('usuario_id', '=', driver_id)])) or bool(request.env['transcash.guia'].search_count([
                    ('company_id', '=', route.company_id.id), ('state', '=', 'registrada'),
                    ('embarque_id', '=', False), ('hoja_ruta_id', '=', False),
                    ('chofer_usuario_id', '=', driver_id)]))
                if not driver_allowed:
                    raise ValidationError(_('El chofer no aparece en la operación disponible.'))
            if provider_id != route.proveedor_id.id:
                provider_allowed = bool(request.env['transcash.chofer'].sudo().search_count([
                    ('company_id', '=', route.company_id.id), ('activo', '=', True),
                    ('empresa_transporte_id', '=', provider_id)])) or bool(request.env['transcash.guia'].search_count([
                    ('company_id', '=', route.company_id.id), ('state', '=', 'registrada'),
                    ('embarque_id', '=', False), ('hoja_ruta_id', '=', False),
                    ('proveedor_id', '=', provider_id)]))
                if not provider_allowed:
                    raise ValidationError(_('El transportista no aparece en la operación disponible.'))
            values = dict(chofer_usuario_id=driver_id, proveedor_id=provider_id,
                          destino_id=destination_id, placa=plate, tipo_vehiculo=vehicle,
                          origen=(post.get('origen') or '').strip()[:240])
            if destination_id != route.destino_id.id:
                # No mantener guías de otro código ERP escondidas en la selección.
                values['seleccion_guia_ids'] = [(5, 0, 0)]
            route.write(values)
            return request.redirect('/transcash/operacion/rutas/%d?ok=modificada' % route.id)
        except (UserError, AccessError, ValidationError) as exc:
            return self._page('Modificar hoja de ruta ' + route.name,
                              section='nueva', form_values=post, tc_route_edit=route,
                              error=str(exc), **self._new_options())

    @http.route('/transcash/operacion/rutas/<int:route_id>/reabrir-edicion', type='http',
                auth='user', website=True, methods=['POST'], csrf=True)
    def tc_reopen_route(self, route_id, **post):
        if not self._guard():
            return request.not_found()
        route = self._route(route_id)
        if not route:
            return request.not_found()
        try:
            with request.env.cr.savepoint():
                result = route.action_tc_reopen_route_for_edit()
            return request.redirect(result['url'])
        except (UserError, AccessError, ValidationError) as exc:
            return request.redirect('/transcash/operacion/rutas/%d?error=%s' % (
                route.id, quote(str(exc)[:320])))
