"""V5.17: PWA interna operativa. Escribe exclusivamente mediante ORM y métodos ya autorizados.
Los usuarios Portal nunca reciben rutas de planificación ni controles financieros.
"""
import base64
from urllib.parse import quote

from odoo import http, _
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.http import request
from odoo.osv import expression
from werkzeug.utils import secure_filename
from .portal import sniff_mime


class TranscashOperaciones(http.Controller):
    OPERATOR = 'logistica_transcash.group_transcash_operador_rutas'
    MANAGER = 'logistica_transcash.group_logistica_manager'
    ERROR_TYPES = (UserError, ValidationError, AccessError, ValueError, TypeError)

    def _operator(self):
        user = request.env.user
        return bool(not user.share and (user.has_group(self.OPERATOR) or user.has_group(self.MANAGER)))

    def _manager(self):
        user = request.env.user
        return bool(not user.share and user.has_group(self.MANAGER))

    def _guard(self):
        return self._operator()

    def _page(self, heading, **data):
        values = {'heading': heading, 'csrf_token': request.csrf_token(), 'error': None, 'ok': None}
        values.update(data)
        response = request.render('logistica_transcash.portal_operacion', values)
        response.headers['Cache-Control'] = 'private, no-store'
        return response

    def _route(self, route_id):
        rec = request.env['transcash.hoja.ruta'].browse(route_id).exists()
        return rec if rec and rec.company_id in request.env.user.company_ids else False

    def _trip(self, trip_id):
        rec = request.env['transcash.embarque'].browse(trip_id).exists()
        return rec if rec and rec.company_id in request.env.user.company_ids else False

    @http.route('/transcash/operacion', type='http', auth='user', website=True, methods=['GET'])
    def home(self, **kw):
        if not self._guard():
            return request.not_found()
        env = request.env
        company = env.company
        dom = [('company_id', 'in', env.user.company_ids.ids)]
        return self._page('Centro de operaciones', section='inicio',
                          contador_rutas=env['transcash.hoja.ruta'].search_count(dom),
                          pendientes=env['transcash.hoja.ruta'].search_count(dom + [('state','=','borrador')]),
                          contador_embarques=env['transcash.embarque'].search_count(dom),
                          pendientes_carga=env['transcash.embarque'].search_count(dom + [('state','=','preparacion')]),
                          company=company)

    @http.route('/transcash/operacion/rutas', type='http', auth='user', website=True, methods=['GET'])
    def route_list(self, **kw):
        if not self._guard():
            return request.not_found()
        rutas = request.env['transcash.hoja.ruta'].search([
            ('company_id','in',request.env.user.company_ids.ids)], order='id desc', limit=180)
        return self._page('Hojas de ruta', section='rutas', rutas=rutas,
                          ok=kw.get('ok'), error=kw.get('error'))

    def _new_options(self):
        env = request.env
        dom = [('company_id','in',env.user.company_ids.ids)]
        choferes = env['transcash.chofer'].sudo().search(dom + [('activo','=',True)], limit=500)
        # Nunca se inventan transportistas ni choferes: solo datos ya registrados.
        guias = env['transcash.guia'].search(dom + [('state','=','registrada'),
            ('embarque_id','=',False), ('hoja_ruta_id','=',False)], limit=500)
        driver_group = env.ref('logistica_transcash.group_transcash_chofer')
        chofer_users = (choferes.mapped('usuario_id') | guias.mapped('chofer_usuario_id')).filtered(
            lambda u: u.share and driver_group in u.sudo().groups_id)
        proveedores = (choferes.mapped('empresa_transporte_id') |
                       guias.mapped('proveedor_id')).filtered(lambda p: bool(p))
        destinos = env['transcash.destino'].search(dom + [('active','=',True)], order='name', limit=500)
        return dict(choferes_pwa=chofer_users.sorted('name'),
                    proveedores_pwa=proveedores.sorted('name'), destinos_pwa=destinos)

    @http.route('/transcash/operacion/rutas/nueva', type='http', auth='user', website=True, methods=['GET','POST'], csrf=True)
    def route_new(self, **post):
        if not self._guard():
            return request.not_found()
        if request.httprequest.method == 'POST':
            try:
                uid = int(post.get('chofer_id') or 0)
                proveedor_id = int(post.get('proveedor_id') or 0)
                destino_id = int(post.get('destino_id') or 0)
                placa = (post.get('placa') or '').strip().upper()
                tipo = post.get('tipo_vehiculo')
                opts = self._new_options()
                if uid not in opts['choferes_pwa'].ids or proveedor_id not in opts['proveedores_pwa'].ids:
                    raise UserError(_('Seleccione un chofer activo y un transportista de los registros disponibles.'))
                if destino_id not in opts['destinos_pwa'].ids:
                    raise UserError(_('Seleccione un destino válido de su compañía.'))
                if not placa or len(placa)>20:
                    raise UserError(_('Introduzca una placa válida (máximo 20 caracteres).'))
                if tipo not in ('mula','camion','camioneta','furgon','otro'):
                    raise UserError(_('Seleccione un tipo de vehículo.'))
                route = request.env['transcash.hoja.ruta'].create({
                    'company_id':request.env.company.id,
                    'chofer_usuario_id':uid, 'proveedor_id':proveedor_id,
                    'destino_id':destino_id, 'placa':placa,
                    'tipo_vehiculo':tipo, 'origen':(post.get('origen') or '').strip()[:240],
                })
                return request.redirect('/transcash/operacion/rutas/%d?ok=creada' % route.id)
            except self.ERROR_TYPES as ex:
                return self._page('Nueva hoja de ruta', section='nueva', error=str(ex),
                                  form_values=post, **self._new_options())
        return self._page('Nueva hoja de ruta', section='nueva', form_values={}, **self._new_options())

    def _candidates(self, route, search):
        Guia = request.env['transcash.guia']
        domain = route._domain_guias_elegibles()
        if search:
            domain = expression.AND([domain, ['|',('name','ilike',search),('numero_documento','ilike',search)]])
        available = Guia.search(domain, order='id desc', limit=400)
        selected = route.seleccion_guia_ids
        rows = []
        for guia in (selected | available).sorted('id', reverse=True):
            eligible = route._es_guia_elegible(guia, permitir_reasignacion=True)
            rows.append(dict(guia=guia, selected=guia in selected,
                             available=eligible, reassign=bool(route._motivos_reasignacion(guia)),
                             reason='Disponible' if eligible else 'No disponible / cambió su estado'))
        return rows[:450]

    @http.route('/transcash/operacion/rutas/<int:route_id>', type='http', auth='user', website=True, methods=['GET'])
    def route_detail(self, route_id, **kw):
        if not self._guard():
            return request.not_found()
        route = self._route(route_id)
        if not route:
            return request.not_found()
        search = (kw.get('buscar') or '').strip()[:90]
        return self._page('Hoja de ruta ' + route.name, section='ruta_detalle', ruta=route,
                          filas=self._candidates(route, search) if route.state == 'borrador' else [],
                          buscar=search, ok=kw.get('ok'), error=kw.get('error'),
                          seleccion_actual=','.join(str(i) for i in sorted(route.seleccion_guia_ids.ids)))

    @http.route('/transcash/operacion/rutas/<int:route_id>/guias', type='http', auth='user', website=True, methods=['POST'], csrf=True)
    def route_select(self, route_id, **post):
        if not self._guard():
            return request.not_found()
        route = self._route(route_id)
        if not route:
            return request.not_found()
        try:
            route._check_operator()
            request.env.cr.execute('SELECT id FROM transcash_hoja_ruta WHERE id=%s FOR UPDATE', (route.id,))
            route.invalidate_recordset(['state','seleccion_guia_ids'])
            if route.state != 'borrador':
                raise UserError(_('La hoja de ruta ya no está en borrador.'))
            old = ','.join(str(i) for i in sorted(route.seleccion_guia_ids.ids))
            if post.get('seleccion_actual') != old:
                raise UserError(_('Otro operador modificó las guías. Recargue la hoja de ruta.'))
            ids = list(dict.fromkeys(int(i) for i in request.httprequest.form.getlist('guias')))
            if len(ids)>100:
                raise UserError(_('Una hoja de ruta admite hasta 100 guías.'))
            selected = request.env['transcash.guia'].browse(ids).exists()
            if len(selected) != len(ids):
                raise UserError(_('Una guía seleccionada ya no existe.'))
            selected.invalidate_recordset(['state','hoja_ruta_id','embarque_id','company_id'])
            if any(not route._es_guia_elegible(g, permitir_reasignacion=True) for g in selected):
                raise UserError(_('Hay guías no disponibles, de otro destino o ya asignadas. Refresque la lista.'))
            mismatches = selected.filtered(lambda g: route._motivos_reasignacion(g))
            if mismatches and post.get('autorizar_reasignacion') != 'on':
                raise UserError(_('Las guías con otro chofer o transportista requieren autorización expresa.'))
            route.write({'seleccion_guia_ids':[(6,0,ids)]})
            # Igual que el asistente V5.15: escritura protegida, auditable y solo operador.
            route.sudo().write({'reasignacion_autorizada':bool(mismatches),
                                'reasignacion_autorizada_por_id':request.env.user.id if mismatches else False})
            return request.redirect('/transcash/operacion/rutas/%d?ok=guardadas' % route.id)
        except self.ERROR_TYPES as ex:
            return request.redirect('/transcash/operacion/rutas/%d?error=%s' % (route.id,quote(str(ex)[:320])))

    @http.route('/transcash/operacion/rutas/<int:route_id>/confirmar', type='http', auth='user', website=True, methods=['POST'], csrf=True)
    def route_confirm(self, route_id, **post):
        if not self._guard():
            return request.not_found()
        route = self._route(route_id)
        if not route:
            return request.not_found()
        try:
            route.action_confirm_route()
            return request.redirect('/transcash/operacion/rutas/%d?ok=confirmada' % route.id)
        except self.ERROR_TYPES as ex:
            return request.redirect('/transcash/operacion/rutas/%d?error=%s' % (route.id,quote(str(ex)[:320])))

    @http.route('/transcash/operacion/rutas/<int:route_id>/video', type='http', auth='user', website=True, methods=['POST'], csrf=True)
    def route_video(self, route_id, **post):
        if not self._guard():
            return request.not_found()
        route = self._route(route_id)
        if not route:
            return request.not_found()
        try:
            if route.state != 'planificada' or not route.embarque_id or route.embarque_id.state != 'preparacion':
                raise UserError(_('Primero incluya esta hoja de ruta en un embarque en preparación.'))
            uploaded = request.httprequest.files.get('video')
            if not uploaded or not uploaded.filename:
                raise UserError(_('Seleccione el video de carga.'))
            data = uploaded.read(75*1024*1024+1)
            mime = sniff_mime(data)
            if len(data)<12 or len(data)>75*1024*1024 or mime not in ('video/mp4','video/webm','video/quicktime'):
                raise UserError(_('Video inválido. Use MP4, MOV o WebM (máximo 75 MB).'))
            route.write({'video_carga':base64.b64encode(data).decode(),
                         'video_nombre':secure_filename(uploaded.filename)[:160] or 'carga.mp4'})
            route.action_validate_video()
            return request.redirect('/transcash/operacion/rutas/%d?ok=video' % route.id)
        except self.ERROR_TYPES as ex:
            return request.redirect('/transcash/operacion/rutas/%d?error=%s' % (route.id,quote(str(ex)[:320])))

    @http.route('/transcash/operacion/embarques/nuevo', type='http', auth='user', website=True, methods=['GET','POST'], csrf=True)
    def trip_new(self, **post):
        if not self._guard():
            return request.not_found()
        Route = request.env['transcash.hoja.ruta']
        ready = Route.search([('company_id','in',request.env.user.company_ids.ids),
                              ('state','in',('planificada','cargada')),('embarque_id','=',False)],
                             order='id desc',limit=240)
        trips = request.env['transcash.embarque'].search([
            ('company_id','in',request.env.user.company_ids.ids),('state','=','preparacion')],
            order='id desc', limit=60)
        if request.httprequest.method == 'POST':
            try:
                ids = list(dict.fromkeys(int(i) for i in request.httprequest.form.getlist('rutas')))
                existing_id = int(post.get('embarque_id') or 0)
                dest_id = int(post.get('destino_cobro_id') or 0)
                if not ids or len(ids)>30:
                    raise UserError(_('Seleccione entre 1 y 30 rutas.'))
                routes = Route.browse(ids).exists()
                if len(routes)!=len(ids) or any(r not in ready for r in routes):
                    raise UserError(_('Alguna ruta ya está asignada o no está lista. Recargue el formulario.'))
                existing = trips.filtered(lambda t:t.id == existing_id)[:1] if existing_id else False
                if existing_id and not existing:
                    raise UserError(_('El embarque seleccionado no está disponible.'))
                wizard = request.env['transcash.armar.embarque.wizard'].create({
                    'ruta_ids':[(6,0,ids)], 'embarque_id':existing.id if existing else False,
                    'destino_cobro_id':dest_id or False})
                result = wizard.action_confirm()  # Permisos, concurrencia y tarifa única del modelo.
                trip_id = result.get('res_id')
                if not trip_id:
                    raise UserError(_('No se pudo identificar el embarque registrado.'))
                return request.redirect('/transcash/operacion/embarques/%d?ok=registrado' % trip_id)
            except self.ERROR_TYPES as ex:
                return self._page('Armar embarque',section='nuevo_embarque', error=str(ex),
                                  form_values=post, rutas_disponibles=ready, embarques_en_preparacion=trips)
        return self._page('Armar embarque',section='nuevo_embarque',form_values={},
                          rutas_disponibles=ready, embarques_en_preparacion=trips)

    @http.route('/transcash/operacion/embarques/<int:trip_id>', type='http', auth='user', website=True, methods=['GET'])
    def trip_detail(self, trip_id, **kw):
        if not self._guard():
            return request.not_found()
        trip = self._trip(trip_id)
        if not trip:
            return request.not_found()
        return self._page('Embarque ' + trip.name,section='embarque_detalle', embarque=trip,
                          error=kw.get('error'),ok=kw.get('ok'))

    @http.route('/transcash/operacion/embarques/<int:trip_id>/liberar', type='http', auth='user', website=True, methods=['POST'], csrf=True)
    def trip_release(self, trip_id, **post):
        if not self._guard():
            return request.not_found()
        trip = self._trip(trip_id)
        if not trip:
            return request.not_found()
        try:
            trip.action_ready_for_driver()
            return request.redirect('/transcash/operacion/embarques/%d?ok=liberado' % trip.id)
        except self.ERROR_TYPES as ex:
            return request.redirect('/transcash/operacion/embarques/%d?error=%s' % (trip.id,quote(str(ex)[:320])))

    @http.route('/transcash/operacion/embarques/<int:trip_id>/reabrir', type='http', auth='user', website=True, methods=['POST'], csrf=True)
    def trip_reopen(self, trip_id, **post):
        if not self._guard():
            return request.not_found()
        trip = self._trip(trip_id)
        if not trip:
            return request.not_found()
        try:
            trip.action_reopen_packing()
            return request.redirect('/transcash/operacion/embarques/%d?ok=reabierto' % trip.id)
        except self.ERROR_TYPES as ex:
            return request.redirect('/transcash/operacion/embarques/%d?error=%s' % (trip.id,quote(str(ex)[:320])))
