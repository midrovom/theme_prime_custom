"""Embarque: operación y negociación; factura y pago en documentos independientes."""
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError, AccessError


class Embarque(models.Model):
    _name = 'transcash.embarque'
    _description = 'Embarque y liquidación de transporte'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc, id desc'

    name = fields.Char('Número de embarque', required=True, copy=False, default='Nuevo', readonly=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company, readonly=True)
    state = fields.Selection([
        ('preparacion', 'Preparación'), ('embarcado', 'Embarcado'),
        ('ruta', 'En ruta'), ('entregado', 'Entregas finalizadas por chofer'),
        ('cancelado', 'Cancelado'),
    ], default='preparacion', required=True, tracking=True, readonly=True, index=True)
    chofer_usuario_id = fields.Many2one('res.users', 'Chofer', required=True, readonly=True, index=True)
    proveedor_id = fields.Many2one('res.partner', 'Empresa de transporte', required=True, readonly=True, index=True)
    placa = fields.Char('Placa', readonly=True)
    origen = fields.Char('Origen de recogida', readonly=True)
    fecha_creacion = fields.Datetime('Creación', default=fields.Datetime.now, readonly=True)
    fecha_embarcado = fields.Datetime('Carga completada', readonly=True, copy=False)
    fecha_salida = fields.Datetime('Salida real', readonly=True, copy=False)
    fecha_entrega = fields.Datetime('Último cierre operativo del chofer', readonly=True, copy=False)
    observacion_general = fields.Text('Observaciones del embarque')
    guia_ids = fields.One2many('transcash.guia', 'embarque_id', string='Guías')
    cantidad_guias = fields.Integer('Guías', compute='_compute_guia_stats')
    guias_entregadas = fields.Integer('Recepciones confirmadas', compute='_compute_guia_stats')
    guias_cerradas_chofer = fields.Integer('Entregas cerradas por chofer', compute='_compute_guia_stats')

    moneda_id = fields.Many2one('res.currency', related='company_id.currency_id', readonly=True)
    valor_acordado = fields.Monetary('Costo total del embarque', currency_field='moneda_id',
            groups='logistica_transcash.group_transcash_contabilidad,logistica_transcash.group_logistica_manager')
    legado_liquidacion_bloqueada = fields.Boolean('Liquidación histórica a conciliar', default=False,
        readonly=True, help='Impide doble cobro de viajes cuyo pago inició en versiones vinculadas a Contabilidad.')
    estado_aprobacion = fields.Selection([
        ('pendiente','Pendiente de aprobación logística'),
        ('aprobado','Aprobado por Logística'),
    ], default='pendiente', required=True, readonly=True, tracking=True)
    aprobacion_excepcional = fields.Boolean('Aprobación con incidencias abiertas', readonly=True, copy=False, default=False)
    motivo_excepcion_pago = fields.Text('Motivo de la autorización excepcional', readonly=True, copy=False)
    excepcion_por_id = fields.Many2one('res.users', 'Autorizado excepcionalmente por', readonly=True, copy=False)
    excepcion_fecha = fields.Datetime('Autorización excepcional', readonly=True, copy=False)
    incidencias_pendientes = fields.Integer('Guías con novedades abiertas', compute='_compute_incidencias_pendientes')
    aprobado_por_id = fields.Many2one('res.users', 'Aprobado por', readonly=True, copy=False)
    aprobado_fecha = fields.Datetime('Fecha de aprobación', readonly=True, copy=False)
    notas_revision_logistica = fields.Text('Revisión del jefe de Logística', readonly=True)
    liquidacion_linea_id = fields.One2many('transcash.pago.liquidacion.linea', 'embarque_id', string='Liquidación documental', readonly=True)
    estado_financiero = fields.Selection([
        ('pendiente','Pendiente de aprobación'),
        ('aprobado','Aprobado / pendiente de liquidación'),
        ('borrador','En preparación por proveedor'),
        ('revision','Factura en revisión'),
        ('observada','Factura observada'),
        ('proceso_pago','En proceso de pago'),
        ('parcial','Pago parcial'),
        ('pagada','Pagado'),
    ], compute='_compute_estado_financiero', string='Estado de pago')

    @api.depends('estado_aprobacion','liquidacion_linea_id.liquidacion_id.estado')
    def _compute_estado_financiero(self):
        for rec in self:
            if rec.liquidacion_linea_id:
                rec.estado_financiero = rec.liquidacion_linea_id[0].liquidacion_id.estado
            else:
                rec.estado_financiero = 'aprobado' if rec.estado_aprobacion == 'aprobado' else 'pendiente'

    @api.depends('guia_ids.incidencia_estado', 'guia_ids.resultado_recepcion', 'guia_ids.rotura_ids.estado')
    def _compute_incidencias_pendientes(self):
        for rec in self:
            rec.incidencias_pendientes = len(rec.guia_ids.filtered(
                lambda g: g.incidencia_estado == 'abierta' or
                g.resultado_recepcion == 'con_novedades' or g.roturas_pendientes))

    _sql_constraints = [
        ('embarque_num_compania_uniq', 'unique(name,company_id)', 'Número de embarque ya registrado.'),
        ('embarque_tarifa_positiva', 'CHECK(valor_acordado >= 0)', 'Costo de flete inválido.'),
    ]

    @api.depends('guia_ids', 'guia_ids.state', 'guia_ids.fecha_cierre_chofer')
    def _compute_guia_stats(self):
        for rec in self:
            rec.cantidad_guias = len(rec.guia_ids)
            rec.guias_entregadas = len(rec.guia_ids.filtered(lambda g: g.state in
                ('entregada','lista_pago','facturada','pagada')))
            rec.guias_cerradas_chofer = len(rec.guia_ids.filtered(lambda g: g.fecha_cierre_chofer or
                g.state in ('entregada','lista_pago','facturada','pagada')))

    # Estados operativos activos: se liberan cuando el chofer cierra TODAS
    # las entregas. La revisión del cliente y la liquidación no lo retienen.
    _ACTIVE_STATES = ('preparacion', 'embarcado', 'ruta')

    @api.model
    def _lock_driver_operation(self, driver_id):
        """Serializa la creación de viajes del mismo chofer entre sesiones/HTTP.

        Dos peticiones con guías distintas podrían pasar un search() normal
        simultáneamente. Advisory lock PostgreSQL transaccional por chofer:
        se libera automáticamente al confirmar o revertir la transacción.
        """
        self.env.cr.execute('SELECT pg_advisory_xact_lock(%s, %s)', (570052, int(driver_id)))

    @api.model
    def _active_driver_trip(self, driver_id, exclude_id=None):
        """Consulta actual de BD, sin depender de la caché ORM de otra pestaña."""
        self.env['transcash.embarque'].flush_model(['state', 'chofer_usuario_id'])
        self.env.cr.execute("""SELECT id FROM transcash_embarque
             WHERE chofer_usuario_id = %s AND state IN ('preparacion','embarcado','ruta')
             AND (%s IS NULL OR id != %s)
             ORDER BY id DESC LIMIT 1""", (int(driver_id), exclude_id, exclude_id))
        match = self.env.cr.fetchone()
        return self.sudo().browse(match[0]) if match else self.browse()

    @api.model_create_multi
    def create(self, vals_list):
        # Solo el flujo controlado de la WebApp crea embarques, incluso con sudo.
        if not self.env.su:
            raise AccessError(_('Cree el embarque desde el flujo autorizado de la WebApp.'))
        seen_drivers = set()
        for vals in vals_list:
            driver_id = vals.get('chofer_usuario_id')
            state = vals.get('state') or 'preparacion'
            if state in self._ACTIVE_STATES:
                if not driver_id:
                    raise UserError(_('El embarque necesita un chofer.'))
                if driver_id in seen_drivers:
                    raise UserError(_('No puede crear dos embarques activos para un mismo chofer.'))
                seen_drivers.add(driver_id)
        for driver_id in sorted(seen_drivers):
            self._lock_driver_operation(driver_id)
            active = self._active_driver_trip(driver_id)
            if active:
                raise UserError(_('Ya tiene el embarque %s en curso (%s). Termínelo antes de crear otro.') %
                                (active.name, dict(self._fields['state'].selection).get(active.state)))
        for vals in vals_list:
            if vals.get('name', 'Nuevo') == 'Nuevo':
                vals['name'] = self.env['ir.sequence'].sudo().next_by_code('transcash.embarque') or 'Nuevo'
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.su:
            protected = {'name','company_id','state','chofer_usuario_id','proveedor_id',
                         'placa','origen','fecha_embarcado','fecha_salida','fecha_entrega',
                         'estado_aprobacion','aprobado_por_id','aprobado_fecha','notas_revision_logistica',
                         'aprobacion_excepcional','motivo_excepcion_pago','excepcion_por_id','excepcion_fecha',
                         'tarifa_id','destino_tarifa_id','tarifa_referencial_total',
                         'objecion_pendiente','observacion_rechazo','objecion_ids'}
            if set(vals) & protected:
                raise AccessError(_('Para cambiar el embarque use las acciones autorizadas.'))
            if set(vals) & {'valor_acordado'}:
                if not self.env.user.has_group('logistica_transcash.group_logistica_manager'):
                    raise AccessError(_('Solo el jefe de Logística negocia la tarifa del viaje.'))
                if any(rec.estado_aprobacion != 'pendiente' or rec.liquidacion_linea_id for rec in self):
                    raise UserError(_('No se puede cambiar el flete aprobado o ya liquidado.'))
            if set(vals) & {'observacion_general'}:
                if not self.env.user.has_group('logistica_transcash.group_logistica_manager'):
                    raise AccessError(_('Use el portal del chofer para registrar observaciones.'))
        # Protege también actualizaciones de estado hechas por acciones RPC,
        # migraciones o sudo: jamás reabra otro viaje activo del mismo chofer.
        if {'state', 'chofer_usuario_id'} & set(vals):
            checks = []
            for trip in self:
                state = vals.get('state', trip.state)
                if state in self._ACTIVE_STATES:
                    driver_id = vals.get('chofer_usuario_id', trip.chofer_usuario_id.id)
                    checks.append((trip.id, driver_id))
            driver_ids = [driver for _, driver in checks]
            if len(driver_ids) != len(set(driver_ids)):
                raise UserError(_('No puede activar dos embarques del mismo chofer al mismo tiempo.'))
            for driver_id in sorted(set(driver_ids)):
                self._lock_driver_operation(driver_id)
            for trip_id, driver_id in checks:
                other = self._active_driver_trip(driver_id, exclude_id=trip_id)
                if other:
                    raise UserError(_('El chofer ya tiene el embarque %s en curso.') % other.name)
        return super().write(vals)

    def unlink(self):
        raise UserError(_('Los embarques se conservan para mantener la trazabilidad.'))

    @api.model
    def create_from_guides(self, guia_ids, observacion=''):
        """Chofer crea un embarque online con las guías que le asignaron en el ERP."""
        user = self.env.user
        if not user.has_group('logistica_transcash.group_transcash_chofer'):
            raise AccessError(_('Solo un chofer habilitado puede crear su embarque desde la WebApp.'))
        try:
            ids = list(dict.fromkeys(int(i) for i in guia_ids))
        except (TypeError, ValueError):
            raise UserError(_('Selección de guías incorrecta.'))
        if not ids or len(ids) > 100:
            raise UserError(_('Seleccione de 1 a 100 guías.'))
        # Bloqueo por chofer, ANTES de bloquear guías: evita dos viajes con guías
        # diferentes en pestañas/teléfonos distintos y mantiene orden de locks.
        self._lock_driver_operation(user.id)
        active = self._active_driver_trip(user.id)
        if active:
            raise UserError(_('Ya tiene el embarque %s en curso. Abra ese embarque para agregar guías nuevas; ' 
                              'solo podrá crear otro cuando cierre todas las entregas del viaje.') % active.name)
        self.env.cr.execute('SELECT id FROM transcash_guia WHERE id = ANY(%s) ORDER BY id FOR UPDATE', (ids,))
        guias = self.env['transcash.guia'].sudo().browse(ids).exists()
        guias.invalidate_recordset(['embarque_id','state'])
        if len(guias) != len(ids):
            raise UserError(_('Una o varias guías no existen.'))
        first = guias[0]
        for g in guias:
            if g.chofer_usuario_id != user or g.state != 'registrada' or g.embarque_id:
                raise AccessError(_('Solo puede agrupar sus guías registradas y aún sin embarque.'))
            if g.company_id != first.company_id or g.proveedor_id != first.proveedor_id or not g.proveedor_id:
                raise UserError(_('Las guías deben pertenecer a la misma empresa proveedora y compañía.'))
            if (g.placa or '').strip().upper() != (first.placa or '').strip().upper():
                raise UserError(_('Las guías de un embarque deben tener la misma placa.'))
        result = self.sudo().create({
            'company_id':first.company_id.id,
            'chofer_usuario_id':user.id,
            'proveedor_id':first.proveedor_id.id,
            'placa':first.placa,
            'origen':first.origen,
            'observacion_general': (observacion or '')[:4000],
        })
        guias.sudo().write({'embarque_id':result.id})
        for g in guias:
            g._track_event('Programada para recogida', publico_cliente=True)
            g._track_event('Vinculada al embarque %s' % result.name, publico_cliente=False)
        return result

    def action_add_guides(self, guia_ids):
        """Anexa guías llegadas por API a un embarque aún en preparación.

        Valida la asignación en BD y serializa contra otros choferes, pestañas
        y la acción "marcar embarcado". No reinicia guías ya cargadas.
        """
        self.ensure_one()
        self._check_driver()
        try:
            ids = list(dict.fromkeys(int(i) for i in guia_ids))
        except (ValueError, TypeError):
            raise UserError(_('Selección de guías incorrecta.'))
        if not ids or len(ids) > 100:
            raise UserError(_('Seleccione entre 1 y 100 guías.'))
        self._lock_driver_operation(self.env.user.id)
        self.env.cr.execute('SELECT id FROM transcash_embarque WHERE id = %s FOR UPDATE', (self.id,))
        self.invalidate_recordset(['state', 'guia_ids'])
        if self.state != 'preparacion':
            raise UserError(_('Solo puede agregar guías mientras el embarque esté en Preparación.'))
        self.env.cr.execute('SELECT id FROM transcash_guia WHERE id = ANY(%s) ORDER BY id FOR UPDATE', (ids,))
        guias = self.env['transcash.guia'].sudo().browse(ids).exists()
        guias.invalidate_recordset(['state', 'embarque_id', 'chofer_usuario_id', 'proveedor_id', 'placa', 'company_id'])
        if len(guias) != len(ids):
            raise UserError(_('Una o varias guías no existen. Actualice la lista.'))
        if len(self.guia_ids) + len(guias) > 100:
            raise UserError(_('El embarque admite como máximo 100 guías.'))
        for guia in guias:
            if guia.chofer_usuario_id != self.env.user:
                raise AccessError(_('Solo puede agregar guías asignadas a su usuario.'))
            if guia.state != 'registrada' or guia.embarque_id:
                raise UserError(_('La guía %s ya tiene un embarque o comenzó su carga.') % guia.name)
            if guia.company_id != self.company_id or guia.proveedor_id != self.proveedor_id:
                raise UserError(_('La guía %s corresponde a otra compañía o empresa de transporte.') % guia.name)
            if (guia.placa or '').strip().upper() != (self.placa or '').strip().upper():
                raise UserError(_('La guía %s tiene una placa distinta a la del embarque.') % guia.name)
        guias.sudo().write({'embarque_id': self.id})
        for guia in guias:
            guia._track_event('Programada para recogida', publico_cliente=True)
            guia._track_event('Agregada posteriormente al embarque %s' % self.name,
                              publico_cliente=False)
        self.message_post(body=_('%s guía(s) agregada(s) mientras el embarque estaba en preparación.') % len(guias))
        return True

    def _check_driver(self):
        for rec in self:
            user = self.env.user
            if rec.chofer_usuario_id != user or not user.has_group('logistica_transcash.group_transcash_chofer'):
                raise AccessError(_('Solo el chofer de este embarque puede ejecutar esta acción.'))

    def _check_dispatch(self):
        if not (self.env.user.has_group('logistica_transcash.group_logistica_bodega') or
                self.env.user.has_group('logistica_transcash.group_logistica_manager')):
            raise AccessError(_('Solo Bodega o Logística puede autorizar la salida.'))
        for rec in self:
            if rec.company_id not in self.env.user.company_ids:
                raise AccessError(_('No tiene autorización para esta compañía.'))
            if not self.env.user.has_group('logistica_transcash.group_logistica_manager'):
                for guia in rec.guia_ids:
                    if guia.bodega_usuario_id != self.env.user:
                        raise AccessError(_('Debe ser responsable de despacho de todas las guías para autorizar su salida.'))

    def action_begin_guide(self, guide_id, observacion=''):
        self.ensure_one()
        self._check_driver()
        guia = self.guia_ids.filtered(lambda g: g.id == int(guide_id))[:1]
        if not guia or self.state != 'preparacion' or guia.state != 'registrada':
            raise UserError(_('El embarque debe estar en preparación y la guía registrada.'))
        guia.sudo().write({'state':'embarque', 'observacion_carga':(observacion or '')[:4000], 'observacion_inicio_carga':(observacion or '')[:4000]})
        guia._track_event('Inicio de carga de la guía', (observacion or '')[:1000])
        return True

    def action_finish_guide(self, guide_id, observacion=''):
        self.ensure_one()
        self._check_driver()
        guia = self.guia_ids.filtered(lambda g: g.id == int(guide_id))[:1]
        if not guia or self.state != 'preparacion' or guia.state != 'embarque':
            raise UserError(_('Esta guía no está en etapa de carga.'))
        # Validar y marcar primero: si Bodega aún no aprobó, no se
        # persiste una observación final de un cierre fallido.
        guia.sudo().action_mark_loaded()
        if observacion:
            guia.sudo().write({'observacion_fin_carga': (observacion or '')[:4000]})
            guia._track_event('Observación final de carga', (observacion or '')[:1000])
        return True

    def action_mark_embarked(self):
        self._check_driver()
        for rec in self:
            # Mismo orden de locks que al añadir: chofer -> embarque.
            self._lock_driver_operation(rec.chofer_usuario_id.id)
            self.env.cr.execute('SELECT id FROM transcash_embarque WHERE id = %s FOR UPDATE', (rec.id,))
            rec.invalidate_recordset(['state', 'guia_ids'])
            if rec.state != 'preparacion' or not rec.guia_ids:
                raise UserError(_('El embarque debe tener guías en preparación.'))
            if any(g.state != 'embarcada' for g in rec.guia_ids):
                raise UserError(_('Primero termine y valide la carga de todas las guías.'))
            rec.sudo().write({'state':'embarcado', 'fecha_embarcado': fields.Datetime.now()})
        return True

    def action_depart(self):
        self._check_dispatch()
        for rec in self:
            if rec.state != 'embarcado' or not rec.guia_ids or any(g.state != 'embarcada' for g in rec.guia_ids):
                raise UserError(_('Todas las guías deben estar cargadas antes de autorizar la salida.'))
            now = fields.Datetime.now()
            rec.guia_ids.sudo().write({'state':'ruta','fecha_salida':now})
            rec.sudo().write({'state':'ruta','fecha_salida':now})
            for g in rec.guia_ids:
                g._track_event('Salida del vehículo autorizada')
        return True

    def _refresh_delivered_state(self):
        """Libera al chofer tras su última entrega, sin esperar al cliente.

        Las guías históricas ya confirmadas cuentan igualmente como cerradas.
        'Entregado' en embarque indica cierre OPERATIVO, no autorización de pago.
        """
        for rec in self.sudo():
            if rec.state == 'ruta' and rec.guia_ids and all(
                    g.fecha_cierre_chofer or g.state in ('entregada','lista_pago','facturada','pagada')
                    for g in rec.guia_ids):
                rec.write({'state':'entregado','fecha_entrega':fields.Datetime.now()})

    def _check_logistics_finance(self):
        if not self.env.user.has_group('logistica_transcash.group_logistica_manager'):
            raise AccessError(_('Solo el jefe de Logística aprueba los fletes.'))
        for rec in self:
            if rec.company_id not in self.env.user.company_ids:
                raise AccessError(_('No está autorizado para esta compañía.'))

    def _ensure_finance_ready(self):
        for rec in self:
            if rec.legado_liquidacion_bloqueada:
                raise UserError(_('Este viaje tenía una liquidación en la versión antigua. Concíliela antes de volver a liquidar.'))
            if rec.state != 'entregado' or not rec.guia_ids:
                raise UserError(_('Todas las guías del embarque deben estar entregadas.'))
            for guia in rec.guia_ids:
                if guia.state not in ('entregada','lista_pago','facturada','pagada'):
                    raise UserError(_('El cliente aún no ha confirmado la recepción de la guía %s.') % guia.name)
                if guia.aprobacion_global != 'aprobada' or guia.roturas_pendientes or guia.incidencia_estado == 'abierta':
                    raise UserError(_('La guía %s aún tiene revisiones, daños o incidencias abiertas.') % guia.name)
                if guia.roturas_aprobadas:
                    notes = guia.nota_credito_id.filtered(lambda n: n.estado == 'emitida' and n.documento_validado_por_id)
                    if not notes:
                        raise UserError(_('Falta confirmar la nota de crédito de la guía %s.') % guia.name)

    def action_open_exception_wizard(self):
        self.ensure_one()
        self._check_logistics_finance()
        if not self.env.user.has_group('logistica_transcash.group_transcash_aprobacion_excepcional'):
            raise AccessError(_('No tiene el permiso adicional de autorización excepcional.'))
        if self.estado_aprobacion != 'pendiente':
            raise UserError(_('Este embarque ya tiene una decisión de aprobación.'))
        return {'type': 'ir.actions.act_window', 'res_model': 'transcash.aprobacion.excepcion.wizard',
                'view_mode': 'form', 'target': 'new', 'name': _('Autorizar flete con incidencias'),
                'context': {'default_embarque_id': self.id}}

    def _approve_exception(self, reason):
        self.ensure_one()
        self._check_logistics_finance()
        if not self.env.user.has_group('logistica_transcash.group_transcash_aprobacion_excepcional'):
            raise AccessError(_('No tiene el permiso especial de aprobación con incidencias.'))
        reason = (reason or '').strip()
        if len(reason) < 15 or len(reason) > 2000:
            raise ValidationError(_('Describa claramente el motivo de la excepción (15 a 2000 caracteres).'))
        # El cierre del chofer es el ÚNICO requisito operativo exceptuado:
        # no exige aceptación del cliente, resolución de NC o roturas.
        self.env.cr.execute('SELECT id FROM transcash_embarque WHERE id = %s FOR UPDATE', (self.id,))
        self.invalidate_recordset(['state','estado_aprobacion','guia_ids'])
        self.env.cr.execute('SELECT id FROM transcash_guia WHERE embarque_id = %s ORDER BY id FOR UPDATE', (self.id,))
        self.guia_ids.invalidate_recordset(['fecha_cierre_chofer','state'])
        if self.estado_aprobacion != 'pendiente' or self.liquidacion_linea_id:
            raise UserError(_('El embarque ya fue aprobado o liquidado.'))
        if self.legado_liquidacion_bloqueada:
            raise UserError(_('Existe una liquidación histórica por conciliar.'))
        if self.state != 'entregado' or not self.guia_ids or any(
                not g.fecha_cierre_chofer and g.state not in ('entregada','lista_pago','facturada','pagada')
                for g in self.guia_ids):
            raise UserError(_('Todas las guías deben tener su entrega cerrada por el chofer.'))
        if not self.proveedor_id or self.valor_acordado <= 0:
            raise UserError(_('Defina empresa transportista y tarifa positiva antes de aprobar.'))
        self.sudo().write({'estado_aprobacion':'aprobado','aprobado_por_id':self.env.uid,
            'aprobado_fecha':fields.Datetime.now(), 'aprobacion_excepcional':True,
            'motivo_excepcion_pago':reason,'excepcion_por_id':self.env.uid,
            'excepcion_fecha':fields.Datetime.now(), 'notas_revision_logistica':reason})
        self.message_post(body=_('APROBACIÓN EXCEPCIONAL con incidencias pendientes. Responsable: %s. Motivo: %s') %
                          (self.env.user.name, reason))
        for g in self.guia_ids:
            g._track_event('Flete autorizado con incidencias pendientes', reason[:600], publico_cliente=False)
        return True

    def action_configure_liquidation(self):
        self.ensure_one()
        self._check_logistics_finance()
        if self.estado_aprobacion != 'pendiente' or self.liquidacion_linea_id:
            raise UserError(_('La tarifa de un embarque aprobado o liquidado no se puede modificar.'))
        return {'type':'ir.actions.act_window', 'res_model':'transcash.tarifa.embarque.wizard',
                'view_mode':'form', 'target':'new', 'name':_('Negociar flete del viaje'),
                'context': {'default_embarque_id':self.id,'default_valor_acordado':self.valor_acordado}}

    def action_approve_transport(self):
        self._check_logistics_finance()
        self._ensure_finance_ready()
        for rec in self:
            if rec.estado_aprobacion != 'pendiente' or rec.liquidacion_linea_id:
                raise UserError(_('Este viaje ya fue aprobado o incluido en una liquidación.'))
            if rec.legado_liquidacion_bloqueada:
                raise UserError(_('El embarque presenta liquidación histórica; no se puede duplicar.'))
            if rec.valor_acordado <= 0 or not rec.proveedor_id:
                raise UserError(_('Defina proveedor y tarifa negociada positiva antes de aprobar.'))
            rec.sudo().write({'estado_aprobacion':'aprobado', 'aprobado_por_id':self.env.uid,
                              'aprobado_fecha':fields.Datetime.now()})
            rec.message_post(body=_('Flete autorizado por Logística: %s %s') %
                (rec.valor_acordado, rec.moneda_id.name))
        return True


class TarifaEmbarqueWizard(models.TransientModel):
    _name = 'transcash.tarifa.embarque.wizard'
    _description = 'Valor negociado por jefe de Logística'

    embarque_id = fields.Many2one('transcash.embarque', required=True, readonly=True)
    valor_acordado = fields.Monetary('Tarifa negociada del embarque', required=True, currency_field='moneda_id')
    moneda_id = fields.Many2one('res.currency', related='embarque_id.moneda_id')

    def action_confirm(self):
        self.ensure_one()
        rec = self.embarque_id
        rec._check_logistics_finance()
        if rec.estado_aprobacion != 'pendiente' or rec.liquidacion_linea_id or self.valor_acordado <= 0:
            raise UserError(_('Solo se puede definir una tarifa positiva antes de la aprobación.'))
        rec.write({'valor_acordado':self.valor_acordado})
        return {'type':'ir.actions.act_window_close'}


class AprobacionExcepcionWizard(models.TransientModel):
    _name = 'transcash.aprobacion.excepcion.wizard'
    _description = 'Justificación de pago excepcional por jefe de Logística'

    embarque_id = fields.Many2one('transcash.embarque', required=True, readonly=True)
    motivo = fields.Text('Motivo de la aprobación excepcional', required=True)

    def action_confirm(self):
        self.ensure_one()
        self.embarque_id._approve_exception(self.motivo)
        return {'type': 'ir.actions.act_window_close'}
