# -*- coding: utf-8 -*-
"""Portal de operaciones: selección estricta de guías por ruta.

Amplía las rutas HTTP existentes de Logística Transcash sin modificar su addon.
El transportista, chofer y destino ya fueron elegidos al crear la hoja de ruta;
no se permite seleccionar guías de terceros ni reasignarlas desde la PWA.
"""
from urllib.parse import quote

from odoo import http, _
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.http import request
from odoo.osv import expression
from odoo.addons.logistica_transcash.controllers.operacion import TranscashOperaciones


class TranscashOperacionFiltrada(TranscashOperaciones):

    @staticmethod
    def _tc_coincide_con_ruta(ruta, guia):
        """Verificación final; nunca se basa en los campos de formulario web."""
        if not (ruta.proveedor_id and ruta.chofer_usuario_id and ruta.destino_id
                and guia.proveedor_id and guia.chofer_usuario_id):
            return False
        if guia.chofer_usuario_id != ruta.chofer_usuario_id:
            return False
        if (guia.proveedor_id.commercial_partner_id !=
                ruta.proveedor_id.commercial_partner_id):
            return False
        return bool(ruta._es_guia_elegible(guia, permitir_reasignacion=False))

    def _candidates(self, route, search):
        """Solo guías coincidentes con transportista + chofer + destino.

        Se añaden las seleccionadas anteriores para permitir desmarcarlas si su
        relación cambió mientras la ruta estaba en borrador. Las discordantes
        figuran deshabilitadas; jamás son seleccionables.
        """
        Guia = request.env['transcash.guia']
        if not (route.proveedor_id and route.chofer_usuario_id and route.destino_id):
            return []
        # Filtro SQL por chofer y empresa comercial; _coincide_destino valida
        # el destino contra el maestro, incluso si el ERP solo envió texto.
        domain = expression.AND([
            route._domain_guias_elegibles(validar_filtros=True),
            [('chofer_usuario_id', '=', route.chofer_usuario_id.id),
             ('proveedor_id.commercial_partner_id', '=',
              route.proveedor_id.commercial_partner_id.id)],
        ])
        if search:
            domain = expression.AND([
                domain,
                ['|', ('name', 'ilike', search),
                 ('numero_documento', 'ilike', search)],
            ])
        # Misma capacidad de la PWA original, sin buscar primero registros
        # irrelevantes de otros choferes o transportistas.
        candidatas = Guia.search(domain, order='id desc', limit=400)
        anteriores = route.seleccion_guia_ids
        filas = []
        for guia in (anteriores | candidatas).sorted('id', reverse=True):
            elegible = self._tc_coincide_con_ruta(route, guia)
            filas.append({
                'guia': guia,
                'selected': elegible and guia in anteriores,
                'available': elegible,
                'reassign': False,
                'reason': ('Coincide con transportista, chofer y destino'
                           if elegible else
                           'No coincide con transportista, chofer o destino; '
                           'retírela de la selección'),
            })
        return filas[:450]

    @http.route()
    def route_detail(self, route_id, **kw):
        """Mantener navegación, permisos y plantilla originales."""
        return super().route_detail(route_id, **kw)

    @http.route()
    def route_select(self, route_id, **post):
        """Impedir por servidor las reasignaciones, incluso con POST manipulado.

        La implementación base sigue comprobando CSRF, permisos, estado,
        token de concurrencia y límite de 100 guías. Aquí bloqueamos antes
        las guías solicitadas y validamos coincidencia estricta.
        """
        if not self._guard():
            return request.not_found()
        ruta = self._route(route_id)
        if not ruta:
            return request.not_found()
        try:
            ruta._check_operator()
            if ruta.state != 'borrador':
                raise UserError(_('La hoja de ruta ya no está en borrador.'))
            form = request.httprequest.form
            valores = form.getlist('guias')
            try:
                ids = list(dict.fromkeys(int(value) for value in valores))
            except (TypeError, ValueError):
                raise UserError(_('La selección contiene identificadores inválidos.'))
            if len(ids) > 100:
                raise UserError(_('Una hoja de ruta admite hasta 100 guías.'))
            # Misma transacción: bloquear la ruta y las guías antes de verificar.
            request.env.cr.execute(
                'SELECT id FROM transcash_hoja_ruta WHERE id = %s FOR UPDATE',
                (ruta.id,),
            )
            ruta.invalidate_recordset(['state', 'seleccion_guia_ids',
                                       'proveedor_id', 'chofer_usuario_id',
                                       'destino_id'])
            if ruta.state != 'borrador':
                raise UserError(_('La ruta fue modificada. Recargue la pantalla.'))
            if ids:
                request.env.cr.execute(
                    'SELECT id FROM transcash_guia WHERE id = ANY(%s) '
                    'ORDER BY id FOR UPDATE', (ids,),
                )
            guias = request.env['transcash.guia'].browse(ids).exists()
            if len(guias) != len(ids):
                raise UserError(_('Una o más guías no existen.'))
            guias.invalidate_recordset([
                'state', 'company_id', 'hoja_ruta_id', 'embarque_id',
                'destino_id', 'destino_codigo', 'destino_ciudad', 'destino',
                'chofer_usuario_id', 'proveedor_id',
            ])
            invalidas = guias.filtered(
                lambda guia: not self._tc_coincide_con_ruta(ruta, guia)
            )
            if invalidas:
                raise UserError(_(
                    'La guía %s no coincide con la empresa transportista, '
                    'el chofer o el destino de la ruta. Seleccione solo '
                    'las guías del resultado filtrado.'
                ) % invalidas[0].name)
            # Ignorar cualquier intento de autorización de cambio: esta PWA
            # siempre utiliza la asociación original de las guías.
            post.pop('autorizar_reasignacion', None)
            return super().route_select(route_id, **post)
        except (UserError, AccessError, ValidationError, ValueError, TypeError) as ex:
            return request.redirect(
                '/transcash/operacion/rutas/%d?error=%s' %
                (ruta.id, quote(str(ex)[:320]))
            )
