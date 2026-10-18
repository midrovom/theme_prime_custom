"""Planificación V5.9: hojas de ruta y tarifas; carga registrada por Logística."""
from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError

TIPO_VEHICULO = [('mula', 'Mula / tractocamión'), ('camion', 'Camión'),
                 ('camioneta', 'Camioneta'), ('furgon', 'Furgón'), ('otro', 'Otro')]


class TarifaTraslado(models.Model):
    _name = 'transcash.tarifa.traslado'
    _description = 'Precio por embarque / viaje según vehículo y destino de cobro'
    _order = 'destino_codigo, tipo_vehiculo'

    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    tipo_vehiculo = fields.Selection(TIPO_VEHICULO, required=True)
    destino_id = fields.Many2one('transcash.destino', string='Destino', index=True, ondelete='restrict')
    destino_codigo = fields.Char('Código destino (histórico)', required=True, index=True, readonly=True)
    destino_nombre = fields.Char('Nombre destino (histórico)', required=True, readonly=True)
    moneda_id = fields.Many2one('res.currency', related='company_id.currency_id')
    precio = fields.Monetary('Valor por viaje (embarque completo)', required=True, currency_field='moneda_id',
        help='Precio de UN embarque, incluso si tiene varias hojas de ruta.')
    _sql_constraints = [
        ('tarifa_tipo_destino_unica', 'unique(company_id,tipo_vehiculo,destino_codigo)',
         'Ya existe una tarifa de ese vehículo para ese destino y compañía.'),
        ('tarifa_positiva', 'CHECK(precio > 0)', 'La tarifa debe ser mayor que cero.'),
    ]

    @api.model
    def _destination_values(self, vals):
        vals = dict(vals)
        dest_id = vals.get('destino_id')
        if not dest_id:
            raise ValidationError(_('Seleccione un destino del maestro de destinos.'))
        dest = self.env['transcash.destino'].sudo().browse(dest_id).exists()
        company_id = vals.get('company_id') or self.env.company.id
        if not dest or not dest.active or dest.company_id.id != company_id:
            raise ValidationError(_('Destino no activo o no corresponde a la compañía.'))
        vals.update(destino_codigo=dest.codigo, destino_nombre=dest.name)
        return vals

    @api.onchange('destino_id')
    def _onchange_destino(self):
        if self.destino_id:
            self.destino_codigo = self.destino_id.codigo
            self.destino_nombre = self.destino_id.name

    @api.model_create_multi
    def create(self, vals_list):
        self._check_edit_permission()
        return super().create([self._destination_values(vals) for vals in vals_list])

    def write(self, vals):
        self._check_edit_permission()
        if 'destino_id' in vals or 'company_id' in vals:
            if len(self) != 1:
                raise UserError(_('Edite el destino de una tarifa a la vez.'))
            vals = self._destination_values(dict(vals, destino_id=vals.get('destino_id',self.destino_id.id),
                                                  company_id=vals.get('company_id',self.company_id.id)))
        elif 'destino_codigo' in vals or 'destino_nombre' in vals:
            raise AccessError(_('El destino solo puede elegirse desde el catálogo.'))
        return super().write(vals)

    def unlink(self):
        self._check_edit_permission()
        if (self.env['transcash.hoja.ruta'].sudo().search_count([('tarifa_id', 'in', self.ids)]) or
                self.env['transcash.embarque'].sudo().search_count([('tarifa_id', 'in', self.ids)])):
            raise UserError(_('Esta tarifa ya fue utilizada en una ruta histórica o embarque: desactívela en lugar de eliminarla.'))
        return super().unlink()

    def _check_edit_permission(self):
        if not self.env.su and not self.env.user.has_group('logistica_transcash.group_logistica_manager'):
            raise AccessError(_('Solo el jefe de Logística administra tarifas.'))


class HojaRuta(models.Model):
    _name = 'transcash.hoja.ruta'
    _description = 'Hoja de ruta planificada por Logística'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(default='Nuevo', copy=False, readonly=True, required=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    chofer_usuario_id = fields.Many2one('res.users', required=True, string='Chofer')
    proveedor_id = fields.Many2one('res.partner', required=True, string='Empresa transportista')
    placa = fields.Char('Placa', required=True)
    tipo_vehiculo = fields.Selection(TIPO_VEHICULO, required=True, default='camion')
    destino_id = fields.Many2one('transcash.destino', string='Destino', index=True, ondelete='restrict')
    destino_codigo = fields.Char('Código destino (histórico)', required=True, readonly=True)
    destino_nombre = fields.Char('Destino / ciudad (histórico)', required=True, readonly=True)
    origen = fields.Char('Origen')
    embarque_id = fields.Many2one('transcash.embarque', readonly=True, index=True, ondelete='restrict')
    # Selección en formulario; en confirmación se asigna la FK real en cada guía.
    seleccion_guia_ids = fields.Many2many('transcash.guia', 'transcash_hoja_ruta_seleccion_rel',
        'ruta_id', 'guia_id', string='Guías seleccionadas', copy=False)
    guia_ids = fields.One2many('transcash.guia', 'hoja_ruta_id', string='Guías confirmadas', readonly=True)
    # Estado OPERATIVO de entrega, independiente de la aceptación del cliente.
    # No sustituye el estado de planificación/carga de la ruta.
    guias_cerradas_chofer = fields.Integer('Guías cerradas por chofer', compute='_compute_entrega_ruta')
    estado_entrega = fields.Selection([
        ('sin_guias', 'Sin guías'), ('pendiente', 'Pendiente de entrega'),
        ('parcial', 'Entregas en curso'), ('completa', 'Ruta entregada'),
    ], string='Estado de entregas', compute='_compute_entrega_ruta')
    fecha_cierre_operativo = fields.Datetime('Última entrega de esta ruta', readonly=True, copy=False)

    @api.depends('guia_ids', 'guia_ids.fecha_cierre_chofer', 'guia_ids.state', 'guia_ids.embarque_id')
    def _compute_entrega_ruta(self):
        for route in self:
            guides = route.guia_ids.filtered(lambda g: not route.embarque_id or g.embarque_id == route.embarque_id)
            closed = len(guides.filtered(lambda g: g.fecha_cierre_chofer or
                g.state in ('entregada', 'lista_pago', 'facturada', 'pagada')))
            route.guias_cerradas_chofer = closed
            route.estado_entrega = ('sin_guias' if not guides else
                                    'completa' if closed == len(guides) else
                                    'parcial' if closed else 'pendiente')

    state = fields.Selection([('borrador','Borrador'),('planificada','Planificada'),
                              ('cargada','Carga documentada'),('aceptada','Aceptada por chofer')],
                             default='borrador', tracking=True, required=True, readonly=True)
    observaciones = fields.Text('Observaciones de Logística')
    evidencia_carga_ids = fields.One2many('transcash.carga.evidencia.ruta', 'ruta_id', string='Bitácora de evidencias de carga', readonly=True)
    cantidad_evidencias_carga = fields.Integer(compute='_compute_cantidad_evidencias_carga', string='Evidencias de carga')
    video_carga = fields.Binary('Video histórico de carga', attachment=True, copy=False)
    video_nombre = fields.Char('Nombre del video', copy=False)
    video_mime = fields.Selection([('video/mp4','MP4'), ('video/webm','WebM'),
                                    ('video/quicktime','MOV')], string='Formato de video', copy=False)
    fecha_video = fields.Datetime(readonly=True, copy=False)
    video_por_id = fields.Many2one('res.users', readonly=True, copy=False)
    # Campos LEGADOS: se conservan para no perder el historial de versiones 5.9–5.15.
    # NO se calculan ni se utilizan para cobrar rutas nuevas.
    tarifa_id = fields.Many2one('transcash.tarifa.traslado', readonly=True)
    moneda_id = fields.Many2one('res.currency', related='company_id.currency_id')
    tarifa_referencial = fields.Monetary(currency_field='moneda_id', readonly=True)
    reasignacion_autorizada = fields.Boolean('Reasignación autorizada por Logística',
                                             copy=False, readonly=True, default=False)
    reasignacion_autorizada_por_id = fields.Many2one('res.users',
        string='Reasignación revisada por', readonly=True, copy=False)

    @api.depends('evidencia_carga_ids', 'video_carga')
    def _compute_cantidad_evidencias_carga(self):
        for route in self:
            route.cantidad_evidencias_carga = len(route.evidencia_carga_ids) + (1 if route.video_carga else 0)

    def _has_carga_evidence(self):
        self.ensure_one()
        return bool(self.evidencia_carga_ids or (self.video_carga and self.video_mime and self.fecha_video))

    @api.model
    def _check_operator(self):
        user = self.env.user
        if user.share or not (user.has_group('logistica_transcash.group_transcash_operador_rutas') or
                             user.has_group('logistica_transcash.group_logistica_manager')):
            raise AccessError(_('Solo Logística puede planificar rutas o evidenciar su carga.'))

    @api.model
    def _destination_values(self, vals):
        vals = dict(vals)
        if not vals.get('destino_id'):
            raise ValidationError(_('Seleccione el destino de la hoja de ruta desde el maestro.'))
        dest = self.env['transcash.destino'].sudo().browse(vals['destino_id']).exists()
        company_id = vals.get('company_id') or self.env.company.id
        if not dest or not dest.active or dest.company_id.id != company_id:
            raise ValidationError(_('Destino no disponible para la compañía.'))
        vals.update(destino_codigo=dest.codigo, destino_nombre=dest.name)
        return vals

    @api.onchange('destino_id')
    def _onchange_destino(self):
        if self.destino_id:
            self.destino_codigo = self.destino_id.codigo
            self.destino_nombre = self.destino_id.name

    # Los filtros del operador son parte de la autorización. Una guía del ERP
    # sin chofer/transportista todavía puede planificarse; una ya asignada a
    # otro chofer o transportista NO se reasigna silenciosamente.
    guias_pendientes_destino = fields.Integer(
        'Pendientes en el destino', compute='_compute_guias_seleccionables')
    guias_disponibles = fields.Integer(
        'Disponibles para esta ruta', compute='_compute_guias_seleccionables')
    cantidad_guias_seleccionadas = fields.Integer(
        'Guías agregadas', compute='_compute_cantidad_guias_seleccionadas')

    @api.depends('seleccion_guia_ids')
    def _compute_cantidad_guias_seleccionadas(self):
        for ruta in self:
            ruta.cantidad_guias_seleccionadas = len(ruta.seleccion_guia_ids)


    @api.model
    def _normalizar_nombre_destino(self, nombre):
        """Comparación exacta normalizada; no se aceptan destinos aproximados."""
        return ' '.join((nombre or '').strip().casefold().split())

    def _coincide_destino(self, guia):
        self.ensure_one()
        if not self.destino_id:
            return False
        # Una vinculación al maestro, si existe, es la fuente definitiva.
        if guia.destino_id:
            return guia.destino_id == self.destino_id
        if (guia.destino_codigo or '').strip():
            return (guia.destino_codigo or '').strip().upper() == self.destino_id.codigo
        # Algunas guías del ERP llegaron con el nombre de ciudad pero SIN código.
        # Se aceptan solo coincidencias exactas en el maestro (sin adivinar).
        nombres = {self._normalizar_nombre_destino(x) for x in
                   (self.destino_id.name, self.destino_id.ciudad) if x}
        return bool(nombres.intersection(self._normalizar_nombre_destino(x) for x in
                                         (guia.destino_ciudad, guia.destino) if x))

    def _motivos_reasignacion(self, guia):
        """Diferencias operativas; NO son cambios de destino ni de compañía."""
        self.ensure_one()
        motivos = []
        if guia.chofer_usuario_id and guia.chofer_usuario_id != self.chofer_usuario_id:
            motivos.append(_('chofer ERP: %s') % guia.chofer_usuario_id.display_name)
        # El ERP puede referenciar un contacto de la misma empresa de transporte.
        if (guia.proveedor_id and self.proveedor_id and
                guia.proveedor_id.commercial_partner_id != self.proveedor_id.commercial_partner_id):
            motivos.append(_('transportista ERP: %s') % guia.proveedor_id.display_name)
        return motivos

    def _domain_guias_elegibles(self, validar_filtros=True):
        """Búsqueda de candidatos: los mismos datos que luego valida el servidor.

        Se permiten guías de la compañía sin ruta ni embarque, aun cuando el ERP
        asignó otro chofer/transporte: el cambio requiere aceptación explícita.
        El destino textual sin código se valida después con _coincide_destino.
        """
        self.ensure_one()
        if not self.company_id or not self.destino_id:
            return [('id', '=', 0)]
        base = [
            ('company_id', '=', self.company_id.id),
            ('state', '=', 'registrada'),
            ('embarque_id', '=', False),
            ('hoja_ruta_id', '=', False),
        ]
        if not validar_filtros:
            return base
        # Prefiltro SQL para no ocultar guías válidas cuando hay miles de
        # registros en otros destinos; validación exacta posterior en Python.
        from odoo.osv import expression
        cod = self.destino_id.codigo
        nombres = list({v for v in (self.destino_id.ciudad, self.destino_id.name) if v})
        opciones = [[('destino_id', '=', self.destino_id.id)],
                    [('destino_codigo', '=ilike', cod)]]
        for nombre in nombres:
            opciones.extend([[('destino_ciudad', '=ilike', nombre)],
                             [('destino', '=ilike', nombre)]])
        return expression.AND([base, expression.OR(opciones)])

    @api.depends('company_id', 'destino_id', 'chofer_usuario_id', 'proveedor_id')
    def _compute_guias_seleccionables(self):
        Guia = self.env['transcash.guia']
        for ruta in self:
            pendientes = Guia.search(ruta._domain_guias_elegibles(validar_filtros=True))
            ruta.guias_pendientes_destino = len(pendientes.filtered(ruta._coincide_destino))
            ruta.guias_disponibles = len(pendientes.filtered(
                lambda guia: ruta._es_guia_elegible(guia, permitir_reasignacion=True))) if (
                    ruta.chofer_usuario_id and ruta.proveedor_id) else 0

    def _es_guia_elegible(self, guia, permitir_reasignacion=False):
        """Una guía nunca cambia de destino ni se duplica en dos rutas."""
        self.ensure_one()
        if (not self.chofer_usuario_id or not self.proveedor_id or
                guia.company_id != self.company_id or guia.state != 'registrada'
                or guia.embarque_id or guia.hoja_ruta_id or not self._coincide_destino(guia)):
            return False
        return permitir_reasignacion or not self._motivos_reasignacion(guia)

    @api.onchange('company_id', 'destino_id', 'chofer_usuario_id', 'proveedor_id')
    def _onchange_filtros_guias(self):
        """Al cambiar los filtros, no dejar selecciones ocultas y equivocadas."""
        if not self.seleccion_guia_ids:
            return
        anteriores = self.seleccion_guia_ids
        validas = anteriores.filtered(lambda g: self._es_guia_elegible(g, permitir_reasignacion=True)) if (
            self.company_id and self.destino_id and self.chofer_usuario_id and self.proveedor_id
        ) else self.env['transcash.guia']
        if len(validas) != len(anteriores):
            descartadas = len(anteriores) - len(validas)
            self.seleccion_guia_ids = validas
            return {'warning': {
                'title': _('Se actualizaron las guías seleccionadas'),
                'message': _('%d guía(s) no coinciden con el destino, chofer o transportista elegidos, o ya están asignadas. Vuelva a revisar la selección.') % descartadas,
            }}

    def action_open_guide_selector(self):
        """Abrir selección múltiple real, sin depender de many2many_tags."""
        self.ensure_one()
        return self.env['transcash.seleccionar.guias.ruta.wizard'].abrir_para_ruta(self)

    def action_view_available_guides(self):
        """Pantalla de diagnóstico: comprobar cuáles guías ofrecen los filtros."""
        self.ensure_one()
        self._check_operator()
        if self.company_id not in self.env.user.company_ids:
            raise AccessError(_('No puede consultar guías de otra compañía.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Guías disponibles para %s') % self.name,
            'res_model': 'transcash.guia', 'view_mode': 'list,form',
            'domain': [('id', 'in', self.env['transcash.guia'].search(
                self._domain_guias_elegibles()).filtered(
                    lambda g: self._es_guia_elegible(g, permitir_reasignacion=True)).ids)],
            'context': {'create': False, 'edit': False, 'delete': False},
            'target': 'current',
        }

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su:
            self._check_operator()
        vals_list = [self._destination_values(vals) for vals in vals_list]
        for vals in vals_list:
            if vals.get('name', 'Nuevo') == 'Nuevo':
                vals['name'] = self.env['ir.sequence'].sudo().next_by_code('transcash.hoja.ruta') or 'RUTA/Nueva'
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.su:
            self._check_operator()
            if {'destino_codigo','destino_nombre'} & set(vals) and 'destino_id' not in vals:
                raise AccessError(_('El destino se selecciona desde el maestro.'))
            forbidden = {'state','embarque_id','guia_ids','tarifa_referencial', 'tarifa_id',
                         'reasignacion_autorizada','reasignacion_autorizada_por_id',
                         'fecha_video','video_por_id'}
            if forbidden & set(vals):
                raise AccessError(_('Los estados y vínculos se cambian con las acciones del flujo.'))
            if any(r.state != 'borrador' for r in self) and {'seleccion_guia_ids','chofer_usuario_id',
                    'proveedor_id','placa','tipo_vehiculo','destino_id','destino_codigo','company_id'} & set(vals):
                raise UserError(_('La ruta ya está confirmada; no altere su composición.'))
            if {'video_carga','video_nombre','video_mime'} & set(vals):
                raise AccessError(_('Registre fotografías o videos desde la bitácora de carga. No se permite reemplazar videos históricos.'))
            if {'video_carga','video_nombre','video_mime'} & set(vals) and any(r.state != 'planificada' or
                    (r.embarque_id and r.embarque_id.state != 'preparacion') for r in self):
                raise UserError(_('El video solo puede incorporarse antes de liberar el embarque al chofer.'))
        if not self.env.su and {'chofer_usuario_id','proveedor_id','destino_id','company_id'} & set(vals):
            vals = dict(vals, reasignacion_autorizada=False, reasignacion_autorizada_por_id=False)
            # write is allowed to clear the flag when editing an unconfirmed route.
        if 'destino_id' in vals or 'company_id' in vals:
            if len(self) != 1:
                raise UserError(_('Cambie el destino de una sola hoja de ruta a la vez.'))
            vals = self._destination_values(dict(vals, destino_id=vals.get('destino_id',self.destino_id.id),
                                                  company_id=vals.get('company_id',self.company_id.id)))
        return super().write(vals)

    def unlink(self):
        self._check_operator()
        if any(r.state != 'borrador' for r in self):
            raise UserError(_('No se puede eliminar una ruta confirmada.'))
        return super().unlink()

    def action_confirm_route(self):
        self._check_operator()
        for ruta in self:
            if ruta.company_id not in self.env.user.company_ids:
                raise AccessError(_('Ruta de una compañía no autorizada.'))
            if not ruta.destino_id or not ruta.destino_id.active:
                raise UserError(_('Seleccione un destino activo en la hoja de ruta.'))
            if ruta.state != 'borrador' or not ruta.seleccion_guia_ids:
                raise UserError(_('Seleccione al menos una guía en una ruta borrador.'))
            guia_ids = sorted(ruta.seleccion_guia_ids.ids)
            self.env.cr.execute('SELECT id FROM transcash_guia WHERE id = ANY(%s) ORDER BY id FOR UPDATE', (guia_ids,))
            guides = ruta.seleccion_guia_ids.sudo()
            guides.invalidate_recordset(['hoja_ruta_id','embarque_id','state',
                'chofer_usuario_id','proveedor_id','destino_id','destino_codigo','destino_ciudad'])
            for guia in guides:
                if not ruta._es_guia_elegible(guia, permitir_reasignacion=True):
                    if guia.chofer_usuario_id and guia.chofer_usuario_id != ruta.chofer_usuario_id:
                        raise UserError(_('La guía %s pertenece al chofer %s. Seleccione el chofer correcto; no se puede reasignar sin revisar la guía.') % (guia.name, guia.chofer_usuario_id.name))
                    if guia.proveedor_id and guia.proveedor_id != ruta.proveedor_id:
                        raise UserError(_('La guía %s está asignada al transportista %s. Seleccione el transportista correcto.') % (guia.name, guia.proveedor_id.display_name))
                    if not ruta._coincide_destino(guia):
                        raise UserError(_('La guía %s tiene otro destino. Verifique el maestro y el código del ERP.') % guia.name)
                    raise UserError(_('La guía %s no está pendiente, ya está asignada o pertenece a otra compañía.') % guia.name)
                if ruta._motivos_reasignacion(guia) and not ruta.reasignacion_autorizada:
                    raise UserError(_('La guía %s tiene un chofer o transportista diferente al de la ruta. '
                                      'Abra «Agregar / quitar guías» y autorice expresamente la reasignación.') % guia.name)
                # El operador escogió el chofer/empresa de la ruta: si la guía
                # difiere, queda constancia individual de la decisión.
            # Planificar una ruta NO exige ni devenga un flete: el transporte cobra
            # una sola vez por embarque, aunque se hagan múltiples entregas.
            for guia in guides:
                changes = {'hoja_ruta_id': ruta.id}
                diferencia = ruta._motivos_reasignacion(guia)
                if guia.chofer_usuario_id != ruta.chofer_usuario_id:
                    changes['chofer_usuario_id'] = ruta.chofer_usuario_id.id
                if guia.proveedor_id != ruta.proveedor_id:
                    changes['proveedor_id'] = ruta.proveedor_id.id
                if (guia.placa or '').strip().upper() != (ruta.placa or '').strip().upper():
                    changes['placa'] = ruta.placa
                guia.sudo().write(changes)
                if diferencia:
                    guia._track_event(_('Reasignación autorizada al confirmar hoja de ruta'),
                        _('Ruta: %(ruta)s. Valores anteriores: %(datos)s. Aprobó: %(usuario)s.') %
                        {'ruta': ruta.name, 'datos': ', '.join(diferencia),
                         'usuario': ruta.reasignacion_autorizada_por_id.display_name or self.env.user.display_name},
                        publico_cliente=False)
                if not guia.destino_id and ruta._coincide_destino(guia):
                    guia.sudo().write({'destino_id': ruta.destino_id.id,
                                       'destino_codigo': ruta.destino_id.codigo})
            ruta.sudo().write({'state':'planificada'})
            for guia in guides:
                guia._track_event('Asignada a hoja de ruta %s' % ruta.name, publico_cliente=False)
        return True

    def action_open_carga_pwa(self):
        self.ensure_one()
        self._check_operator()
        if not self.embarque_id or self.embarque_id.state != 'preparacion':
            raise UserError(_('Primero incluya la ruta en un embarque en preparación.'))
        return {'type':'ir.actions.act_url',
                'url':'/transcash/operacion/embarques/%d#ruta-%d' % (self.embarque_id.id, self.id),
                'target':'self'}

    def action_open_video(self):
        self.ensure_one()
        self._check_operator()
        if not self.video_carga or self.state not in ('cargada','aceptada'):
            raise UserError(_('Valide primero el video de carga.'))
        return {'type':'ir.actions.act_url','url':'/transcash/rutas/%d/video' % self.id, 'target':'new'}

    def action_validate_video(self):
        self._check_operator()
        for ruta in self:
            if ruta.company_id not in self.env.user.company_ids:
                raise AccessError(_('Ruta de una compañía no autorizada.'))
            if ruta.state != 'planificada' or not ruta.embarque_id or ruta.embarque_id.state != 'preparacion':
                raise UserError(_('La ruta debe estar en un embarque en preparación.'))
            if not ruta.video_carga or not ruta.video_nombre:
                raise UserError(_('Adjunte un video real de carga para esta ruta.'))
            import base64
            data = base64.b64decode(ruta.video_carga)
            if len(data) < 12 or len(data) > 75*1024*1024:
                raise UserError(_('Video no válido: el tamaño máximo es 75 MB.'))
            mime = 'video/webm' if data.startswith(b'\x1a\x45\xdf\xa3') and b'webm' in data[:128].lower() else (
                'video/quicktime' if data[4:12] == b'ftypqt  ' else (
                'video/mp4' if len(data) >= 12 and data[4:8] == b'ftyp' and data[8:12] in
                (b'isom',b'iso2',b'iso4',b'iso5',b'iso6',b'mp41',b'mp42',b'avc1',b'M4V ') else False))
            if mime not in ('video/mp4','video/webm','video/quicktime'):
                raise UserError(_('Solo se admite video MP4, WebM o MOV válido.'))
            ruta.sudo().write({'state':'cargada','video_mime':mime,
                'fecha_video':fields.Datetime.now(),'video_por_id':self.env.uid})
        return True


class EmbarqueRuta(models.Model):
    _inherit = 'transcash.embarque'

    ruta_ids = fields.One2many('transcash.hoja.ruta', 'embarque_id', string='Hojas de ruta')
    # Mantenemos la misma columna almacenada de V5.15 para preservar importes
    # históricos. Ahora se registra UN precio por viaje, sin dependencias de rutas.
    tarifa_referencial_total = fields.Monetary(
        'Valor referencial del VIAJE', currency_field='moneda_id', readonly=True, copy=False,
        help='Tarifa capturada una sola vez al armar el embarque. No se suman las hojas de ruta.')
    tarifa_id = fields.Many2one('transcash.tarifa.traslado',
        string='Tarifario aplicado al viaje', readonly=True, copy=False, ondelete='restrict')
    destino_tarifa_id = fields.Many2one('transcash.destino',
        string='Destino de cobro del viaje', readonly=True, copy=False, ondelete='restrict',
        help='Destino principal elegido para aplicar una sola tarifa al embarque completo.')
    tipo_vehiculo = fields.Selection(TIPO_VEHICULO, string='Tipo de vehículo')

    aceptado_chofer = fields.Boolean('Carga aceptada por chofer', readonly=True, copy=False)
    fecha_aceptacion_chofer = fields.Datetime(readonly=True, copy=False)
    observacion_rechazo = fields.Text('Última objeción de carga', readonly=True)
    objecion_pendiente = fields.Boolean('Objeción del chofer pendiente', default=False, readonly=True,
                                       copy=False, index=True)
    objecion_ids = fields.One2many('transcash.embarque.objecion', 'embarque_id',
                                   string='Bitácora interna de objeciones', readonly=True)
    objeciones_count = fields.Integer('Veces objetado', compute='_compute_objeciones_count')

    @api.depends('objecion_ids')
    def _compute_objeciones_count(self):
        for emb in self:
            emb.objeciones_count = len(emb.objecion_ids)

    def _exigir_evidencia_correccion(self):
        """No reutilizar imágenes antiguas después de que el chofer objetó la carga."""
        self.ensure_one()
        abierta = self.objecion_ids.filtered(lambda o: o.estado == 'abierta')[:1]
        if not abierta:
            return True  # compatibilidad con observaciones de versiones previas
        for ruta in self.ruta_ids:
            nuevas = ruta.evidencia_carga_ids.filtered(lambda e: e.fecha >= abierta.fecha)
            video_nuevo = ruta.video_carga and ruta.fecha_video and ruta.fecha_video >= abierta.fecha
            if not (nuevas or video_nuevo):
                raise UserError(_('Registre una NUEVA foto o video de corrección para la ruta %s.') % ruta.name)
        return True

    def action_resolve_discrepancy(self, explanation):
        """Solo Operador/Jefe logístico, con corrección escrita y nuevas evidencias."""
        self.ensure_one()
        self.env['transcash.hoja.ruta']._check_operator()
        if self.company_id not in self.env.user.company_ids:
            raise AccessError(_('Compañía no autorizada.'))
        explanation = (explanation or '').strip()
        if len(explanation) < 12 or len(explanation) > 2000:
            raise ValidationError(_('Describa la solución aplicada (12 a 2000 caracteres).'))
        self._lock_driver_operation(self.chofer_usuario_id.id)
        self.env.cr.execute('SELECT id FROM transcash_embarque WHERE id=%s FOR UPDATE', (self.id,))
        self.invalidate_recordset(['state','objecion_pendiente','observacion_rechazo','ruta_ids'])
        if self.state != 'preparacion' or not (self.objecion_pendiente or self.observacion_rechazo):
            raise UserError(_('Solo puede resolver una objeción durante la preparación del embarque.'))
        if any(r.state != 'cargada' or not r._has_carga_evidence() for r in self.ruta_ids):
            raise UserError(_('Complete las evidencias de todas las hojas de ruta antes de resolver.'))
        self._exigir_evidencia_correccion()
        abiertas = self.objecion_ids.filtered(lambda o: o.estado == 'abierta')
        if abiertas:
            abiertas.sudo().write({'estado':'resuelta','responsable_id':self.env.user.id,
                                  'fecha_resolucion':fields.Datetime.now(),
                                  'explicacion_resolucion':explanation})
        else:
            # Legado V5.18: conservar también la objeción escrita antes de este modelo.
            self.env['transcash.embarque.objecion'].sudo().create({
                'embarque_id':self.id,'chofer_id':self.chofer_usuario_id.id,
                'fecha':fields.Datetime.now(), 'motivo':self.observacion_rechazo or 'Objeción histórica',
                'estado':'resuelta','responsable_id':self.env.user.id,
                'fecha_resolucion':fields.Datetime.now(), 'explicacion_resolucion':explanation})
        self.sudo().write({'objecion_pendiente':False,'observacion_rechazo':False})
        return True

    def action_ready_for_driver(self):
        """Operador cierra la preparación; el chofer debe aceptar y salir."""
        self.env['transcash.hoja.ruta']._check_operator()
        for emb in self:
            if emb.company_id not in self.env.user.company_ids:
                raise AccessError(_('Compañía no autorizada.'))
            self._lock_driver_operation(emb.chofer_usuario_id.id)
            self.env.cr.execute('SELECT id FROM transcash_embarque WHERE id=%s FOR UPDATE', (emb.id,))
            emb.invalidate_recordset(['state','ruta_ids'])
            if emb.state != 'preparacion' or not emb.ruta_ids:
                raise UserError(_('Agregue hojas de ruta antes de liberar el embarque.'))
            if any(r.state != 'cargada' or not r._has_carga_evidence() for r in emb.ruta_ids):
                raise UserError(_('Antes de liberar el viaje, registre al menos una foto o video de CADA hoja de ruta.'))
            if emb.objecion_pendiente or emb.observacion_rechazo:
                raise UserError(_('El chofer objetó la carga. Primero corrija la evidencia y registre la solución.'))
            guides = emb.ruta_ids.mapped('guia_ids')
            if not guides or set(guides.ids) != set(emb.guia_ids.ids):
                raise UserError(_('Las guías del embarque y de sus rutas no coinciden.'))
            guides.sudo().write({'state':'embarcada'})
            emb.sudo().write({'state':'embarcado','fecha_embarcado':fields.Datetime.now(),
                              'observacion_rechazo':False,'objecion_pendiente':False})
            for guide in guides:
                guide._track_event('Carga evidenciada por Logística y puesta a disposición del chofer', publico_cliente=False)
        return True

    def action_accept_and_depart(self):
        """Aceptación del conductor con una sola pulsación; inicia traslado."""
        self._check_driver()
        for emb in self:
            self._lock_driver_operation(emb.chofer_usuario_id.id)
            self.env.cr.execute('SELECT id FROM transcash_embarque WHERE id=%s FOR UPDATE', (emb.id,))
            emb.invalidate_recordset(['state','aceptado_chofer','ruta_ids'])
            if emb.aceptado_chofer and emb.state == 'ruta':
                continue  # reintento seguro en caso de interrupción HTTP
            if emb.state != 'embarcado' or not emb.ruta_ids:
                raise UserError(_('El embarque aún no está listo para su aceptación.'))
            if emb.objecion_pendiente or emb.observacion_rechazo:
                raise UserError(_('Logística debe corregir y volver a liberar el embarque observado.'))
            if any(r.state != 'cargada' or not r._has_carga_evidence() for r in emb.ruta_ids):
                raise UserError(_('Falta evidencia de carga en alguna hoja de ruta.'))
            if any(g.state != 'embarcada' for g in emb.guia_ids):
                raise UserError(_('Existen guías que no están listas para salir.'))
            now = fields.Datetime.now()
            emb.guia_ids.sudo().write({'state':'ruta','fecha_salida':now})
            emb.ruta_ids.sudo().write({'state':'aceptada'})
            emb.sudo().write({'state':'ruta','aceptado_chofer':True,
                              'fecha_aceptacion_chofer':now,'fecha_salida':now})
            for guia in emb.guia_ids:
                guia._track_event('Chofer aceptó carga de hoja de ruta e inició traslado', publico_cliente=False)
        return True

    def action_report_discrepancy(self, reason):
        """Objeción privada PRE-SALIDA, con bloqueo transaccional e historial."""
        self.ensure_one()
        self._check_driver()
        reason = (reason or '').strip()
        if len(reason) < 12 or len(reason) > 2000:
            raise ValidationError(_('Explique el motivo de la objeción (12 a 2000 caracteres).'))
        self._lock_driver_operation(self.chofer_usuario_id.id)
        self.env.cr.execute('SELECT id FROM transcash_embarque WHERE id=%s FOR UPDATE', (self.id,))
        self.invalidate_recordset(['state','objecion_pendiente','observacion_rechazo','ruta_ids'])
        if self.state != 'embarcado' or not self.ruta_ids or self.aceptado_chofer:
            raise UserError(_('Solo puede objetar un embarque pendiente de aceptación y antes de la salida.'))
        if self.objecion_pendiente or self.observacion_rechazo:
            raise UserError(_('Ya existe una objeción pendiente. Logística debe revisarla.'))
        self.env['transcash.embarque.objecion'].sudo().create({
            'embarque_id':self.id,'chofer_id':self.env.user.id,
            'fecha':fields.Datetime.now(),'motivo':reason})
        self.sudo().write({'observacion_rechazo':reason,'objecion_pendiente':True})
        return True

    def action_open_resolver_objecion(self):
        self.ensure_one()
        self.env['transcash.hoja.ruta']._check_operator()
        if self.company_id not in self.env.user.company_ids:
            raise AccessError(_('Compañía no autorizada.'))
        if self.state != 'preparacion' or not (self.objecion_pendiente or self.observacion_rechazo):
            raise UserError(_('No hay ninguna objeción en preparación para resolver.'))
        return {'type':'ir.actions.act_window','res_model':'transcash.resolver.objecion.wizard',
                'view_mode':'form','target':'new','name':_('Resolver objeción de carga'),
                'context':{'default_embarque_id':self.id}}

    def action_reopen_packing(self):
        self.env['transcash.hoja.ruta']._check_operator()
        for emb in self:
            if emb.state != 'embarcado' or emb.aceptado_chofer or not emb.ruta_ids:
                raise UserError(_('Solo puede devolver a preparación antes de que el chofer acepte.'))
            emb.guia_ids.sudo().write({'state':'registrada'})
            emb.ruta_ids.sudo().write({'state':'planificada'})
            emb.sudo().write({'state':'preparacion',
                              'objecion_pendiente':bool(emb.objecion_pendiente or emb.observacion_rechazo)})
        return True

    def action_depart(self):
        """Los viajes V5.9 parten exclusivamente con la aceptación del conductor."""
        for rec in self:
            if rec.ruta_ids:
                raise UserError(_('La salida de un embarque planificado requiere aceptación del chofer en la WebApp.'))
        return super().action_depart()

    @api.model
    def create_from_guides(self, guia_ids, observacion=''):
        raise AccessError(_('Los embarques los crea Logística usando hojas de ruta.'))

    def action_add_guides(self, guia_ids):
        raise AccessError(_('Solo Logística puede agregar hojas de ruta a un embarque en preparación.'))

    def action_begin_guide(self, guide_id, observacion=''):
        raise AccessError(_('La carga es documentada por Logística, no por el chofer.'))

    def action_finish_guide(self, guide_id, observacion=''):
        raise AccessError(_('La carga es documentada por Logística, no por el chofer.'))

    def action_mark_embarked(self):
        raise AccessError(_('Solo Logística puede liberar la carga desde las hojas de ruta.'))


class ArmarEmbarqueWizard(models.TransientModel):
    _name = 'transcash.armar.embarque.wizard'
    _description = 'Agrupar hojas de ruta en un embarque'

    embarque_id = fields.Many2one('transcash.embarque', readonly=True)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company, required=True)
    proveedor_id = fields.Many2one('res.partner', string='Empresa transportista')
    chofer_usuario_id = fields.Many2one('res.users', string='Chofer')
    tipo_vehiculo = fields.Selection(TIPO_VEHICULO, string='Tipo de vehículo')
    placa = fields.Char('Placa')
    ruta_disponible_ids = fields.Many2many('transcash.hoja.ruta', compute='_compute_rutas_disponibles')
    ruta_ids = fields.Many2many('transcash.hoja.ruta', string='Hojas de ruta compatibles', required=True)

    @api.depends('company_id', 'proveedor_id', 'chofer_usuario_id', 'tipo_vehiculo', 'placa', 'embarque_id')
    def _compute_rutas_disponibles(self):
        for wizard in self:
            if not wizard.proveedor_id or not wizard.chofer_usuario_id or not wizard.tipo_vehiculo or not wizard.placa:
                wizard.ruta_disponible_ids = False
                continue
            wizard.ruta_disponible_ids = self.env['transcash.hoja.ruta'].search([
                ('company_id', '=', wizard.company_id.id),
                ('proveedor_id', '=', wizard.proveedor_id.id),
                ('chofer_usuario_id', '=', wizard.chofer_usuario_id.id),
                ('tipo_vehiculo', '=', wizard.tipo_vehiculo),
                ('placa', '=ilike', wizard.placa.strip()),
                ('embarque_id', '=', False),
                ('state', 'in', ('planificada', 'cargada')),
            ])

    @api.onchange('embarque_id')
    def _onchange_trip_selection(self):
        if self.embarque_id:
            self.company_id = self.embarque_id.company_id
            self.proveedor_id = self.embarque_id.proveedor_id
            self.chofer_usuario_id = self.embarque_id.chofer_usuario_id
            self.tipo_vehiculo = self.embarque_id.tipo_vehiculo
            self.placa = self.embarque_id.placa

    @api.onchange('company_id', 'proveedor_id', 'chofer_usuario_id', 'tipo_vehiculo', 'placa')
    def _onchange_route_filters(self):
        self.ruta_ids = self.ruta_ids.filtered(lambda r:
            r.company_id == self.company_id and r.proveedor_id == self.proveedor_id and
            r.chofer_usuario_id == self.chofer_usuario_id and r.tipo_vehiculo == self.tipo_vehiculo and
            (r.placa or '').strip().upper() == (self.placa or '').strip().upper())

    destino_cobro_id = fields.Many2one('transcash.destino',
        string='Destino para tarifa del viaje',
        help='Seleccione UNO de los destinos de las rutas. Se cobra una vez por embarque, no por ruta.')
    destinos_posibles_ids = fields.Many2many('transcash.destino',
        compute='_compute_destinos_posibles', string='Destinos de las rutas')
    moneda_id = fields.Many2one('res.currency', compute='_compute_resumen_tarifa', readonly=True)
    importe_total_estimado = fields.Monetary('VALOR POR EMBARQUE COMPLETO',
        currency_field='moneda_id', compute='_compute_resumen_tarifa', readonly=True)

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        emb_id = values.get('embarque_id') or self.env.context.get('default_embarque_id')
        if emb_id:
            trip = self.env['transcash.embarque'].browse(emb_id)
            for name, value in [('company_id',trip.company_id.id), ('proveedor_id',trip.proveedor_id.id),
                                ('chofer_usuario_id',trip.chofer_usuario_id.id), ('tipo_vehiculo',trip.tipo_vehiculo),
                                ('placa',trip.placa)]:
                values[name] = value
        return values

    @api.model_create_multi
    def create(self, vals_list):
        # Compatibilidad con invocaciones históricas del asistente: inferir filtros
        # si el código existente ya proporcionó rutas; validar SIEMPRE al confirmar.
        for vals in vals_list:
            ids = []
            for command in vals.get('ruta_ids') or []:
                if command[0] == 6:
                    ids += command[2]
                elif command[0] == 4:
                    ids.append(command[1])
            if vals.get('embarque_id'):
                trip = self.env['transcash.embarque'].browse(vals['embarque_id'])
                first = trip
            elif ids:
                first = self.env['transcash.hoja.ruta'].browse(ids[0])
            else:
                first = False
            if first:
                for key in ('company_id','proveedor_id','chofer_usuario_id','tipo_vehiculo','placa'):
                    value = getattr(first, key)
                    vals.setdefault(key, value.id if key.endswith('_id') else value)
        return super().create(vals_list)

    @api.depends('ruta_ids', 'ruta_ids.destino_id')
    def _compute_destinos_posibles(self):
        for wizard in self:
            wizard.destinos_posibles_ids = wizard.ruta_ids.mapped('destino_id')

    @api.onchange('ruta_ids', 'embarque_id')
    def _onchange_rutas_precio(self):
        """Sugerir destino solo cuando es inequívoco; nunca adivinar en multiruta."""
        if self.embarque_id:
            self.destino_cobro_id = self.embarque_id.destino_tarifa_id
            return
        destinos = self.ruta_ids.mapped('destino_id')
        if self.destino_cobro_id not in destinos:
            self.destino_cobro_id = destinos if len(destinos) == 1 else False

    @api.model
    def _buscar_tarifa_viaje(self, company, tipo, destino):
        if not company or not tipo or not destino:
            return self.env['transcash.tarifa.traslado']
        return self.env['transcash.tarifa.traslado'].sudo().search([
            ('company_id', '=', company.id), ('tipo_vehiculo', '=', tipo),
            ('destino_id', '=', destino.id), ('active', '=', True)], limit=1)

    @api.depends('ruta_ids', 'ruta_ids.tipo_vehiculo', 'ruta_ids.destino_id',
                 'destino_cobro_id', 'embarque_id', 'embarque_id.tarifa_referencial_total')
    def _compute_resumen_tarifa(self):
        """Vista previa de UN SOLO flete por embarque; sin sumar rutas."""
        for wizard in self:
            first = wizard.ruta_ids[:1]
            company = wizard.embarque_id.company_id or (first.company_id if first else self.env.company)
            wizard.moneda_id = company.currency_id
            if wizard.embarque_id:
                wizard.importe_total_estimado = wizard.embarque_id.tarifa_referencial_total
                continue
            destinos = wizard.ruta_ids.mapped('destino_id')
            destino = wizard.destino_cobro_id or (destinos if len(destinos) == 1 else False)
            tarifa = self._buscar_tarifa_viaje(company, first.tipo_vehiculo if first else False, destino)
            wizard.importe_total_estimado = tarifa.precio if tarifa else 0.0

    def action_confirm(self):
        self.ensure_one()
        self.env['transcash.hoja.ruta']._check_operator()
        if not self.ruta_ids:
            raise UserError(_('Seleccione al menos una hoja de ruta.'))
        routes = self.ruta_ids.sorted('id')
        first = routes[0]
        if not self.proveedor_id or not self.chofer_usuario_id or not self.tipo_vehiculo or not self.placa:
            raise UserError(_('Seleccione primero transportista, chofer, tipo de vehículo y placa.'))
        if (first.company_id != self.company_id or first.proveedor_id != self.proveedor_id or
                first.chofer_usuario_id != self.chofer_usuario_id or first.tipo_vehiculo != self.tipo_vehiculo or
                (first.placa or '').strip().upper() != self.placa.strip().upper()):
            raise UserError(_('La ruta seleccionada no coincide con los datos planificados para el viaje.'))
        if self.embarque_id and (self.embarque_id.company_id != self.company_id or
                self.embarque_id.proveedor_id != self.proveedor_id or
                self.embarque_id.chofer_usuario_id != self.chofer_usuario_id or
                self.embarque_id.tipo_vehiculo != self.tipo_vehiculo or
                (self.embarque_id.placa or '').strip().upper() != self.placa.strip().upper()):
            raise UserError(_('El embarque existente tiene otro transporte, chofer o tipo de vehículo.'))
        if first.company_id not in self.env.user.company_ids:
            raise AccessError(_('Compañía no autorizada.'))
        driver = first.chofer_usuario_id.id
        trip_model = self.env['transcash.embarque']
        trip_model._lock_driver_operation(driver)
        existing = self.embarque_id
        if existing:
            if existing.company_id not in self.env.user.company_ids:
                raise AccessError(_('Compañía no autorizada.'))
            self.env.cr.execute('SELECT id FROM transcash_embarque WHERE id=%s FOR UPDATE', (existing.id,))
            existing.invalidate_recordset(['state'])
            if existing.state != 'preparacion' or existing.chofer_usuario_id != first.chofer_usuario_id:
                raise UserError(_('Solo se agregan rutas a un embarque en preparación del mismo chofer.'))
        elif trip_model._active_driver_trip(driver):
            raise UserError(_('Este chofer ya tiene un embarque activo. Agregue rutas al existente.'))
        for route in routes:
            if route.state not in ('planificada','cargada') or route.embarque_id:
                raise UserError(_('La hoja %s no está disponible o ya tiene embarque.') % route.name)
            if (route.company_id != first.company_id or route.chofer_usuario_id != first.chofer_usuario_id or
                route.proveedor_id != first.proveedor_id or
                (route.placa or '').strip().upper() != (first.placa or '').strip().upper() or
                route.tipo_vehiculo != first.tipo_vehiculo):
                raise UserError(_('Las rutas deben compartir compañía, chofer, transporte, placa y tipo de vehículo.'))
        tarifa_viaje = False
        destino_cobro = False
        if not existing:
            destinos = routes.mapped('destino_id')
            destino_cobro = self.destino_cobro_id or (destinos if len(destinos) == 1 else False)
            if not destino_cobro or destino_cobro not in destinos:
                raise UserError(_('Seleccione el destino de cobro ENTRE LOS DESTINOS de las rutas seleccionadas.'))
            tarifa_viaje = self._buscar_tarifa_viaje(first.company_id, first.tipo_vehiculo, destino_cobro)
            if not tarifa_viaje or tarifa_viaje.precio <= 0:
                raise UserError(_('No hay precio por viaje para %(vehiculo)s hacia %(destino)s. '
                                  'Configure el maestro de fletes antes de armar el embarque.') %
                                {'vehiculo': first.tipo_vehiculo, 'destino': destino_cobro.display_name})
            existing = trip_model.sudo().create({'company_id':first.company_id.id,
                'chofer_usuario_id':driver,'proveedor_id':first.proveedor_id.id,
                'placa':first.placa,'origen':first.origen,'tipo_vehiculo':first.tipo_vehiculo,
                'destino_tarifa_id':destino_cobro.id, 'tarifa_id':tarifa_viaje.id,
                'tarifa_referencial_total':tarifa_viaje.precio,
                'valor_acordado':tarifa_viaje.precio})
        if existing and (existing.company_id != first.company_id or existing.proveedor_id != first.proveedor_id or
                         (existing.placa or '').strip().upper() != (first.placa or '').strip().upper() or
                         existing.tipo_vehiculo != first.tipo_vehiculo):
            raise UserError(_('El embarque y las rutas no corresponden a la misma empresa, placa o vehículo.'))
        if len(existing.guia_ids) + len(routes.mapped('guia_ids')) > 100:
            raise UserError(_('Excede el máximo de 100 guías por embarque.'))
        guides = routes.mapped('guia_ids')
        if not guides or any(g.embarque_id for g in guides):
            raise UserError(_('Alguna ruta no tiene guías disponibles.'))
        # Añadir rutas a un mismo viaje NO genera otro cargo ni modifica el
        # valor acordado, la tarifa capturada o la liquidación. Esto también
        # preserva importes históricos de embarques creados antes de V5.16.
        routes.sudo().write({'embarque_id':existing.id})
        guides.sudo().write({'embarque_id':existing.id})
        return {'type':'ir.actions.act_window', 'res_model':'transcash.embarque',
                'res_id':existing.id, 'view_mode':'form', 'target':'current'}


class CorregirTarifaEmbarqueWizard(models.TransientModel):
    _name = 'transcash.corregir.tarifa.embarque.wizard'
    _description = 'Revisar la tarifa única de un embarque existente'

    embarque_id = fields.Many2one('transcash.embarque', required=True, readonly=True)
    destino_cobro_id = fields.Many2one('transcash.destino', string='Destino para cobrar viaje', required=True)
    destinos_posibles_ids = fields.Many2many('transcash.destino', compute='_compute_destinos')
    moneda_id = fields.Many2one('res.currency', related='embarque_id.moneda_id')
    valor_sugerido = fields.Monetary('Nuevo valor referencial del viaje',
        currency_field='moneda_id', compute='_compute_valor_sugerido')
    actualizar_valor_acordado = fields.Boolean('Actualizar también el valor negociado', default=False,
        help='Solo marque esta opción si Logística desea reemplazar expresamente el importe anterior.')

    @api.depends('embarque_id', 'embarque_id.ruta_ids', 'embarque_id.ruta_ids.destino_id')
    def _compute_destinos(self):
        for wizard in self:
            wizard.destinos_posibles_ids = wizard.embarque_id.ruta_ids.mapped('destino_id')

    @api.depends('embarque_id', 'embarque_id.tipo_vehiculo', 'destino_cobro_id')
    def _compute_valor_sugerido(self):
        tarifa_model = self.env['transcash.tarifa.traslado'].sudo()
        for wizard in self:
            emb = wizard.embarque_id
            tarifa = tarifa_model.search([
                ('company_id', '=', emb.company_id.id),
                ('tipo_vehiculo', '=', emb.tipo_vehiculo),
                ('destino_id', '=', wizard.destino_cobro_id.id),
                ('active', '=', True)], limit=1) if emb and wizard.destino_cobro_id else tarifa_model
            wizard.valor_sugerido = tarifa.precio if len(tarifa) == 1 else 0.0

    def action_confirm(self):
        self.ensure_one()
        trip = self.embarque_id
        trip._check_logistics_finance()
        self.env.cr.execute('SELECT id FROM transcash_embarque WHERE id=%s FOR UPDATE', (trip.id,))
        trip.invalidate_recordset(['estado_aprobacion', 'liquidacion_linea_id', 'ruta_ids', 'tipo_vehiculo'])
        if trip.estado_aprobacion != 'pendiente' or trip.liquidacion_linea_id:
            raise UserError(_('Un flete ya aprobado o liquidado no puede repriciarse.'))
        if not trip.ruta_ids or self.destino_cobro_id not in trip.ruta_ids.mapped('destino_id'):
            raise UserError(_('El destino de cobro debe pertenecer a las rutas de este embarque.'))
        tarifa = self.env['transcash.tarifa.traslado'].sudo().search([
            ('company_id', '=', trip.company_id.id),
            ('tipo_vehiculo', '=', trip.tipo_vehiculo),
            ('destino_id', '=', self.destino_cobro_id.id),
            ('active', '=', True)], limit=1)
        if not tarifa or tarifa.precio <= 0:
            raise UserError(_('No existe una tarifa activa para ese vehículo y destino.'))
        antes_referencia, antes_negociado = trip.tarifa_referencial_total, trip.valor_acordado
        values = {'destino_tarifa_id': self.destino_cobro_id.id,
                  'tarifa_id': tarifa.id, 'tarifa_referencial_total': tarifa.precio}
        if self.actualizar_valor_acordado:
            values['valor_acordado'] = tarifa.precio
        trip.sudo().write(values)
        trip.message_post(body=_('Revisión de tarifa única por %s: referencial %s → %s; '
                                 'acordado anterior %s; actualizar acordado: %s.') %
                          (self.env.user.display_name, antes_referencia, tarifa.precio,
                           antes_negociado, _('Sí') if self.actualizar_valor_acordado else _('No')))
        return {'type': 'ir.actions.act_window_close'}


class GuiaRuta(models.Model):
    _inherit = 'transcash.guia'
    hoja_ruta_id = fields.Many2one('transcash.hoja.ruta', index=True, copy=False,
        readonly=True, string='Hoja de ruta')

    def action_mark_loaded(self):
        if any(g.hoja_ruta_id for g in self):
            raise AccessError(_('Las guías de hoja de ruta se documentan y liberan desde Logística.'))
        return super().action_mark_loaded()


class EvidenciaRuta(models.Model):
    _inherit = 'transcash.evidencia'

    @api.model
    def register_evidence(self, guia, tipo, observacion, file_data, filename, mime,
                          tipo_novedad='ninguna', rotura_id=False):
        if tipo == 'carga':
            raise AccessError(_('El chofer no registra evidencia de carga: Logística carga un video por hoja de ruta.'))
        if tipo == 'novedad' and guia.chofer_usuario_id == self.env.user and not rotura_id:
            raise AccessError(_('Las novedades de la carga se declaran desde Logística. El chofer registra la entrega.'))
        return super().register_evidence(guia, tipo, observacion, file_data, filename, mime,
                                         tipo_novedad=tipo_novedad, rotura_id=rotura_id)

class EmbarqueRutasActions(models.Model):
    _inherit = 'transcash.embarque'

    @api.model
    def action_open_create_embarque(self):
        self.env['transcash.hoja.ruta']._check_operator()
        return {'type':'ir.actions.act_window', 'name':_('Armar embarque con rutas'),
                'res_model':'transcash.armar.embarque.wizard','view_mode':'form',
                'target':'new'}

    def action_open_reprice_trip(self):
        self.ensure_one()
        self._check_logistics_finance()
        if self.estado_aprobacion != 'pendiente' or self.liquidacion_linea_id:
            raise UserError(_('Solo puede revisar tarifas de embarques no aprobados ni liquidados.'))
        return {'type': 'ir.actions.act_window', 'name': _('Revisar tarifa única del embarque'),
                'res_model': 'transcash.corregir.tarifa.embarque.wizard', 'view_mode': 'form',
                'target': 'new', 'context': {'default_embarque_id': self.id,
                'default_destino_cobro_id': self.destino_tarifa_id.id}}

    def action_open_add_routes(self):
        self.ensure_one()
        self.env['transcash.hoja.ruta']._check_operator()
        if self.state != 'preparacion':
            raise UserError(_('Solo se agregan rutas antes de liberar el embarque.'))
        return {'type':'ir.actions.act_window', 'name':_('Agregar rutas al embarque'),
                'res_model':'transcash.armar.embarque.wizard','view_mode':'form',
                'target':'new','context':{'default_embarque_id':self.id}}

class GuiaEntregaFirmada(models.Model):
    _inherit = 'transcash.guia'

    firma_receptor = fields.Binary('Firma de persona que recibe', attachment=True, readonly=True, copy=False)
    firma_receptor_fecha = fields.Datetime('Fecha de firma', readonly=True, copy=False)

    def action_close_driver_delivery(self, observation='', contact_name='', firma_png=None):
        self.ensure_one()
        if self.fecha_cierre_chofer:
            return super().action_close_driver_delivery(observation, contact_name)
        if self.hoja_ruta_id:
            import base64
            if not firma_png or not firma_png.startswith('data:image/png;base64,'):
                raise ValidationError(_('Solicite y registre la firma de quien recibe antes de finalizar.'))
            try:
                decoded = base64.b64decode(firma_png.split(',', 1)[1], validate=True)
            except Exception as exc:
                raise ValidationError(_('La firma capturada no es válida.')) from exc
            if not decoded.startswith(b'\x89PNG\r\n\x1a\n') or not (100 < len(decoded) < 400000):
                raise ValidationError(_('La firma debe ser PNG válido de menos de 400 KB.'))
            # Validar primero estado, autor, receptor y foto en la implementación existente.
            result = super().action_close_driver_delivery(observation, contact_name)
            self.sudo().write({'firma_receptor': base64.b64encode(decoded).decode('ascii'),
                               'firma_receptor_fecha': fields.Datetime.now()})
            self._track_event('Firma de recepción capturada por el chofer',
                              'Firma declarada por %s' % (contact_name or '')[:160])
            return result
        return super().action_close_driver_delivery(observation, contact_name)

class RoturaRuta(models.Model):
    _inherit = 'transcash.rotura'

    @api.model
    def register_damage(self, guia, linea, cantidad, observacion, archivos):
        if guia.hoja_ruta_id and guia.chofer_usuario_id == self.env.user and self.env.user.has_group('logistica_transcash.group_transcash_chofer'):
            raise AccessError(_('El chofer registra la entrega; los reportes de rotura corresponden al cliente y Ventas.'))
        return super().register_damage(guia, linea, cantidad, observacion, archivos)
