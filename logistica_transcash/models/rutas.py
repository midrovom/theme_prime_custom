"""Planificación V5.9: hojas de ruta y tarifas; carga registrada por Logística."""
from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError

TIPO_VEHICULO = [('mula', 'Mula / tractocamión'), ('camion', 'Camión'),
                 ('camioneta', 'Camioneta'), ('furgon', 'Furgón'), ('otro', 'Otro')]


class TarifaTraslado(models.Model):
    _name = 'transcash.tarifa.traslado'
    _description = 'Tarifa de transporte por vehículo y destino'
    _order = 'destino_codigo, tipo_vehiculo'

    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    tipo_vehiculo = fields.Selection(TIPO_VEHICULO, required=True)
    destino_id = fields.Many2one('transcash.destino', string='Destino', index=True, ondelete='restrict')
    destino_codigo = fields.Char('Código destino (histórico)', required=True, index=True, readonly=True)
    destino_nombre = fields.Char('Nombre destino (histórico)', required=True, readonly=True)
    moneda_id = fields.Many2one('res.currency', related='company_id.currency_id')
    precio = fields.Monetary(required=True, currency_field='moneda_id')
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
        if self.env['transcash.hoja.ruta'].sudo().search_count([('tarifa_id', 'in', self.ids)]):
            raise UserError(_('Esta tarifa ya fue usada: desactívela en lugar de eliminarla.'))
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
    state = fields.Selection([('borrador','Borrador'),('planificada','Planificada'),
                              ('cargada','Carga documentada'),('aceptada','Aceptada por chofer')],
                             default='borrador', tracking=True, required=True, readonly=True)
    observaciones = fields.Text('Observaciones de Logística')
    video_carga = fields.Binary('Video de carga por ruta', attachment=True, copy=False)
    video_nombre = fields.Char('Nombre del video', copy=False)
    video_mime = fields.Selection([('video/mp4','MP4'), ('video/webm','WebM'),
                                    ('video/quicktime','MOV')], string='Formato de video', copy=False)
    fecha_video = fields.Datetime(readonly=True, copy=False)
    video_por_id = fields.Many2one('res.users', readonly=True, copy=False)
    tarifa_id = fields.Many2one('transcash.tarifa.traslado', readonly=True)
    moneda_id = fields.Many2one('res.currency', related='company_id.currency_id')
    tarifa_referencial = fields.Monetary(currency_field='moneda_id', readonly=True)

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


    def _domain_guias_elegibles(self, validar_filtros=True):
        """Único criterio compartido por los contadores y el selector en la vista.

        destino_id manda. Se admite código ERP histórico únicamente cuando la
        guía todavía no tiene destino_id (migraciones o registros antiguos).
        """
        self.ensure_one()
        if not self.company_id or not self.destino_id:
            return [('id', '=', 0)]
        domain = [
            ('company_id', '=', self.company_id.id),
            ('state', '=', 'registrada'),
            ('embarque_id', '=', False),
            ('hoja_ruta_id', '=', False),
            '|', ('destino_id', '=', self.destino_id.id),
            '&', ('destino_id', '=', False), ('destino_codigo', '=', self.destino_id.codigo),
        ]
        if validar_filtros:
            if not self.chofer_usuario_id or not self.proveedor_id:
                return [('id', '=', 0)]
            domain.extend([
                '|', ('chofer_usuario_id', '=', False),
                     ('chofer_usuario_id', '=', self.chofer_usuario_id.id),
                '|', ('proveedor_id', '=', False),
                     ('proveedor_id', '=', self.proveedor_id.id),
            ])
        return domain

    @api.depends('company_id', 'destino_id', 'chofer_usuario_id', 'proveedor_id')
    def _compute_guias_seleccionables(self):
        Guia = self.env['transcash.guia']
        for ruta in self:
            ruta.guias_pendientes_destino = Guia.search_count(
                ruta._domain_guias_elegibles(validar_filtros=False))
            ruta.guias_disponibles = Guia.search_count(
                ruta._domain_guias_elegibles(validar_filtros=True))

    def _es_guia_elegible(self, guia):
        """Revisión final del servidor, incluso si se evita el filtro de UI."""
        self.ensure_one()
        if (guia.company_id != self.company_id or guia.state != 'registrada'
                or guia.embarque_id or guia.hoja_ruta_id):
            return False
        if guia.destino_id:
            if guia.destino_id != self.destino_id:
                return False
        elif (guia.destino_codigo or '').strip().upper() != self.destino_id.codigo:
            return False
        if guia.chofer_usuario_id and guia.chofer_usuario_id != self.chofer_usuario_id:
            return False
        if guia.proveedor_id and guia.proveedor_id != self.proveedor_id:
            return False
        return True

    @api.onchange('company_id', 'destino_id', 'chofer_usuario_id', 'proveedor_id')
    def _onchange_filtros_guias(self):
        """Al cambiar los filtros, no dejar selecciones ocultas y equivocadas."""
        if not self.seleccion_guia_ids:
            return
        anteriores = self.seleccion_guia_ids
        validas = anteriores.filtered(lambda g: self._es_guia_elegible(g)) if (
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
            'domain': self._domain_guias_elegibles(),
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
                         'fecha_video','video_por_id'}
            if forbidden & set(vals):
                raise AccessError(_('Los estados y vínculos se cambian con las acciones del flujo.'))
            if any(r.state != 'borrador' for r in self) and {'seleccion_guia_ids','chofer_usuario_id',
                    'proveedor_id','placa','tipo_vehiculo','destino_id','destino_codigo','company_id'} & set(vals):
                raise UserError(_('La ruta ya está confirmada; no altere su composición.'))
            if {'video_carga','video_nombre','video_mime'} & set(vals) and any(r.state != 'planificada' or
                    (r.embarque_id and r.embarque_id.state != 'preparacion') for r in self):
                raise UserError(_('El video solo puede incorporarse antes de liberar el embarque al chofer.'))
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
            guides.invalidate_recordset(['hoja_ruta_id','embarque_id','state'])
            for guia in guides:
                if not ruta._es_guia_elegible(guia):
                    if guia.chofer_usuario_id and guia.chofer_usuario_id != ruta.chofer_usuario_id:
                        raise UserError(_('La guía %s pertenece al chofer %s. Seleccione el chofer correcto; no se puede reasignar sin revisar la guía.') % (guia.name, guia.chofer_usuario_id.name))
                    if guia.proveedor_id and guia.proveedor_id != ruta.proveedor_id:
                        raise UserError(_('La guía %s está asignada al transportista %s. Seleccione el transportista correcto.') % (guia.name, guia.proveedor_id.display_name))
                    if (guia.destino_id != ruta.destino_id if guia.destino_id else
                            (guia.destino_codigo or '').strip().upper() != ruta.destino_id.codigo):
                        raise UserError(_('La guía %s tiene otro destino. Verifique el maestro y el código del ERP.') % guia.name)
                    raise UserError(_('La guía %s no está pendiente, ya está asignada o pertenece a otra compañía.') % guia.name)
                # Se completan campos aún no asignados por el ERP; nunca se pisa
                # un chofer o transportista diferente en una guía ya importada.
            tarifa = self.env['transcash.tarifa.traslado'].sudo().search([
                ('company_id','=',ruta.company_id.id),('tipo_vehiculo','=',ruta.tipo_vehiculo),
                ('destino_id','=',ruta.destino_id.id),('active','=',True)], limit=1)
            if not tarifa:
                raise UserError(_('Configure una tarifa para vehículo %s, destino %s.') %
                                (ruta.tipo_vehiculo, ruta.destino_codigo))
            for guia in guides:
                changes = {'hoja_ruta_id': ruta.id}
                if guia.chofer_usuario_id != ruta.chofer_usuario_id:
                    changes['chofer_usuario_id'] = ruta.chofer_usuario_id.id
                if guia.proveedor_id != ruta.proveedor_id:
                    changes['proveedor_id'] = ruta.proveedor_id.id
                if (guia.placa or '').strip().upper() != (ruta.placa or '').strip().upper():
                    changes['placa'] = ruta.placa
                guia.sudo().write(changes)
            ruta.sudo().write({'state':'planificada','tarifa_id':tarifa.id,'tarifa_referencial':tarifa.precio})
            for guia in guides:
                guia._track_event('Asignada a hoja de ruta %s' % ruta.name)
        return True

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
    tarifa_referencial_total = fields.Monetary(
        'Valor referencial del embarque', currency_field='moneda_id',
        compute='_compute_tarifa_referencial_total', store=True, readonly=True,
        help='Suma de las tarifas capturadas en las hojas de ruta, sin recalcular el precio histórico desde el maestro.')
    tipo_vehiculo = fields.Selection(TIPO_VEHICULO, string='Tipo de vehículo')

    @api.depends('ruta_ids', 'ruta_ids.tarifa_referencial')
    def _compute_tarifa_referencial_total(self):
        for trip in self:
            trip.tarifa_referencial_total = sum(trip.ruta_ids.mapped('tarifa_referencial'))

    aceptado_chofer = fields.Boolean('Carga aceptada por chofer', readonly=True, copy=False)
    fecha_aceptacion_chofer = fields.Datetime(readonly=True, copy=False)
    observacion_rechazo = fields.Text('Discrepancia reportada por chofer', readonly=True)

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
            if any(r.state != 'cargada' or not r.video_carga for r in emb.ruta_ids):
                raise UserError(_('Cada hoja de ruta debe tener su video de carga validado.'))
            guides = emb.ruta_ids.mapped('guia_ids')
            if not guides or set(guides.ids) != set(emb.guia_ids.ids):
                raise UserError(_('Las guías del embarque y de sus rutas no coinciden.'))
            guides.sudo().write({'state':'embarcada'})
            emb.sudo().write({'state':'embarcado','fecha_embarcado':fields.Datetime.now(),
                              'observacion_rechazo':False})
            for guide in guides:
                guide._track_event('Carga evidenciada por Logística y puesta a disposición del chofer')
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
            if emb.observacion_rechazo:
                raise UserError(_('Logística debe corregir y volver a liberar el embarque observado.'))
            if any(r.state != 'cargada' or not r.video_carga for r in emb.ruta_ids):
                raise UserError(_('Falta un video válido de alguna ruta.'))
            if any(g.state != 'embarcada' for g in emb.guia_ids):
                raise UserError(_('Existen guías que no están listas para salir.'))
            now = fields.Datetime.now()
            emb.guia_ids.sudo().write({'state':'ruta','fecha_salida':now})
            emb.ruta_ids.sudo().write({'state':'aceptada'})
            emb.sudo().write({'state':'ruta','aceptado_chofer':True,
                              'fecha_aceptacion_chofer':now,'fecha_salida':now})
            for guia in emb.guia_ids:
                guia._track_event('Chofer aceptó carga de hoja de ruta e inició traslado')
        return True

    def action_report_discrepancy(self, reason):
        self._check_driver()
        if self.state != 'embarcado' or not self.ruta_ids:
            raise UserError(_('Solo puede observar un embarque pendiente de aceptación.'))
        if len((reason or '').strip()) < 8:
            raise ValidationError(_('Describa brevemente la diferencia encontrada.'))
        self.sudo().write({'observacion_rechazo': reason[:2000]})
        self.message_post(body=_('Chofer reportó diferencia antes de salir: %s') % reason[:500])
        return True

    def action_reopen_packing(self):
        self.env['transcash.hoja.ruta']._check_operator()
        for emb in self:
            if emb.state != 'embarcado' or emb.aceptado_chofer or not emb.ruta_ids:
                raise UserError(_('Solo puede devolver a preparación antes de que el chofer acepte.'))
            emb.guia_ids.sudo().write({'state':'registrada'})
            emb.ruta_ids.sudo().write({'state':'planificada'})
            emb.sudo().write({'state':'preparacion','observacion_rechazo':False})
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
    ruta_ids = fields.Many2many('transcash.hoja.ruta', string='Hojas de ruta', required=True)
    moneda_id = fields.Many2one('res.currency', compute='_compute_resumen_tarifas', readonly=True)
    importe_nuevas_rutas = fields.Monetary('Valor de rutas seleccionadas',
        currency_field='moneda_id', compute='_compute_resumen_tarifas', readonly=True)
    importe_rutas_existentes = fields.Monetary('Valor de rutas ya incluidas',
        currency_field='moneda_id', compute='_compute_resumen_tarifas', readonly=True)
    importe_total_estimado = fields.Monetary('VALOR REFERENCIAL DEL EMBARQUE',
        currency_field='moneda_id', compute='_compute_resumen_tarifas', readonly=True)

    @api.depends('ruta_ids', 'ruta_ids.tarifa_referencial',
                 'embarque_id', 'embarque_id.ruta_ids.tarifa_referencial',
                 'embarque_id.company_id')
    def _compute_resumen_tarifas(self):
        """Vista previa reactiva: no guarda ni negocia montos antes de confirmar."""
        for wizard in self:
            company = (wizard.embarque_id.company_id or
                       (wizard.ruta_ids[0].company_id if wizard.ruta_ids else self.env.company))
            wizard.moneda_id = company.currency_id
            wizard.importe_nuevas_rutas = sum(wizard.ruta_ids.mapped('tarifa_referencial'))
            wizard.importe_rutas_existentes = sum(
                wizard.embarque_id.ruta_ids.mapped('tarifa_referencial'))
            wizard.importe_total_estimado = (
                wizard.importe_nuevas_rutas + wizard.importe_rutas_existentes)

    def action_confirm(self):
        self.ensure_one()
        self.env['transcash.hoja.ruta']._check_operator()
        if not self.ruta_ids:
            raise UserError(_('Seleccione al menos una hoja de ruta.'))
        routes = self.ruta_ids.sorted('id')
        first = routes[0]
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
        if not existing:
            existing = trip_model.sudo().create({'company_id':first.company_id.id,
                'chofer_usuario_id':driver,'proveedor_id':first.proveedor_id.id,
                'placa':first.placa,'origen':first.origen,'tipo_vehiculo':first.tipo_vehiculo})
        if existing and (existing.company_id != first.company_id or existing.proveedor_id != first.proveedor_id or
                         (existing.placa or '').strip().upper() != (first.placa or '').strip().upper() or
                         existing.tipo_vehiculo != first.tipo_vehiculo):
            raise UserError(_('El embarque y las rutas no corresponden a la misma empresa, placa o vehículo.'))
        if len(existing.guia_ids) + len(routes.mapped('guia_ids')) > 100:
            raise UserError(_('Excede el máximo de 100 guías por embarque.'))
        guides = routes.mapped('guia_ids')
        if not guides or any(g.embarque_id for g in guides):
            raise UserError(_('Alguna ruta no tiene guías disponibles.'))
        old_reference = sum(existing.ruta_ids.mapped('tarifa_referencial'))
        old_negotiated = existing.valor_acordado
        routes.sudo().write({'embarque_id':existing.id})
        guides.sudo().write({'embarque_id':existing.id})
        # Valor sugerido; Logística conserva la posibilidad de negociar y ajustar el total.
        if existing.estado_aprobacion == 'pendiente' and (not old_negotiated or abs(old_negotiated - old_reference) < 0.00001):
            existing.sudo().write({'valor_acordado':sum(existing.ruta_ids.mapped('tarifa_referencial'))})
        return {'type':'ir.actions.act_window', 'res_model':'transcash.embarque',
                'res_id':existing.id, 'view_mode':'form', 'target':'current'}


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
