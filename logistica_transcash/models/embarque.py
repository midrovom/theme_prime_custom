"""Embarque: unidad de salida física y factura de flete; las guías retienen sus daños."""
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
        ('ruta', 'En ruta'), ('entregado', 'Entregado'),
        ('cancelado', 'Cancelado'),
    ], default='preparacion', required=True, tracking=True, readonly=True, index=True)
    chofer_usuario_id = fields.Many2one('res.users', 'Chofer', required=True, readonly=True, index=True)
    proveedor_id = fields.Many2one('res.partner', 'Empresa de transporte', required=True, readonly=True, index=True)
    placa = fields.Char('Placa', readonly=True)
    origen = fields.Char('Origen de recogida', readonly=True)
    fecha_creacion = fields.Datetime('Creación', default=fields.Datetime.now, readonly=True)
    fecha_embarcado = fields.Datetime('Carga completada', readonly=True, copy=False)
    fecha_salida = fields.Datetime('Salida real', readonly=True, copy=False)
    fecha_entrega = fields.Datetime('Última entrega', readonly=True, copy=False)
    observacion_general = fields.Text('Observaciones del embarque')
    guia_ids = fields.One2many('transcash.guia', 'embarque_id', string='Guías')
    cantidad_guias = fields.Integer('Guías', compute='_compute_guia_stats')
    guias_entregadas = fields.Integer('Entregadas', compute='_compute_guia_stats')

    moneda_id = fields.Many2one('res.currency', related='company_id.currency_id', readonly=True)
    valor_acordado = fields.Monetary('Costo total del embarque', currency_field='moneda_id',
            groups='logistica_transcash.group_transcash_contabilidad,logistica_transcash.group_logistica_manager')
    cuenta_gasto_id = fields.Many2one('account.account', 'Cuenta de gasto',
            domain="[('account_type','in',['expense','expense_direct_cost'])]",
            groups='logistica_transcash.group_transcash_contabilidad,logistica_transcash.group_logistica_manager')
    factura_id = fields.Many2one('account.move', 'Factura de transporte', readonly=True, copy=False,
            groups='logistica_transcash.group_transcash_contabilidad,logistica_transcash.group_logistica_manager')
    pago_estado = fields.Selection([('pendiente','No liquidado'), ('autorizado','Autorizado'),
        ('facturado','Factura registrada'), ('pagado','Pagado')], default='pendiente',
        required=True, readonly=True, tracking=True,
        groups='logistica_transcash.group_transcash_contabilidad,logistica_transcash.group_logistica_manager')

    _sql_constraints = [
        ('embarque_num_compania_uniq', 'unique(name,company_id)', 'Número de embarque ya registrado.'),
        ('embarque_tarifa_positiva', 'CHECK(valor_acordado >= 0)', 'Costo de flete inválido.'),
    ]

    @api.depends('guia_ids', 'guia_ids.state')
    def _compute_guia_stats(self):
        for rec in self:
            rec.cantidad_guias = len(rec.guia_ids)
            rec.guias_entregadas = len(rec.guia_ids.filtered(lambda g: g.state in
                ('entregada','lista_pago','facturada','pagada')))

    # Estados que impiden iniciar otro viaje. "Embarcado" no equivale a
    # "terminado": también hay que entregar todas las guías.
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
                         'factura_id','pago_estado'}
            if set(vals) & protected:
                raise AccessError(_('Para cambiar el embarque use las acciones autorizadas.'))
            if set(vals) & {'valor_acordado','cuenta_gasto_id'}:
                if not self.env.user.has_group('logistica_transcash.group_transcash_contabilidad'):
                    raise AccessError(_('Solo Contabilidad configura el costo de los embarques.'))
                if any(rec.pago_estado != 'pendiente' for rec in self):
                    raise UserError(_('El costo no se modifica luego de aprobar la liquidación.'))
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
                              'solo podrá crear otro cuando el actual esté entregado.') % active.name)
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
        for rec in self.sudo():
            if rec.state == 'ruta' and rec.guia_ids and all(g.state in
                    ('entregada','lista_pago','facturada','pagada') for g in rec.guia_ids):
                rec.write({'state':'entregado','fecha_entrega':fields.Datetime.now()})

    def _check_accounting(self):
        if not self.env.user.has_group('logistica_transcash.group_transcash_contabilidad'):
            raise AccessError(_('Solo Contabilidad puede liquidar embarques.'))
        for rec in self:
            if rec.company_id not in self.env.user.company_ids:
                raise AccessError(_('No tiene acceso contable a la compañía del embarque.'))

    def _ensure_finance_ready(self):
        for rec in self:
            if rec.state != 'entregado' or not rec.guia_ids:
                raise UserError(_('Todas las guías del embarque deben estar entregadas.'))
            for guia in rec.guia_ids:
                if guia.aprobacion_global != 'aprobada' or guia.roturas_pendientes or guia.incidencia_estado == 'abierta':
                    raise UserError(_('La guía %s aún tiene revisiones, daños o incidencias abiertas.') % guia.name)
                if guia.roturas_aprobadas:
                    notes = guia.nota_credito_id.filtered(lambda n: n.estado == 'emitida' and n.documento_validado_por_id)
                    if not notes:
                        raise UserError(_('Falta confirmar la nota de crédito de la guía %s.') % guia.name)

    def action_configure_liquidation(self):
        self.ensure_one()
        self._check_accounting()
        if self.pago_estado != 'pendiente':
            raise UserError(_('El embarque ya está en proceso de liquidación.'))
        return {'type':'ir.actions.act_window', 'name':_('Costo del embarque'),
                'res_model':'transcash.embarque.liquidacion.wizard', 'view_mode':'form',
                'target':'new', 'context':{'default_embarque_id':self.id,
                    'default_valor_acordado':self.valor_acordado,
                    'default_cuenta_gasto_id':self.cuenta_gasto_id.id or False}}

    def action_ready_payment(self):
        self._check_accounting()
        self._ensure_finance_ready()
        for rec in self:
            if rec.pago_estado != 'pendiente' or not rec.proveedor_id or not rec.cuenta_gasto_id or rec.valor_acordado <= 0:
                raise UserError(_('Configure proveedor, costo positivo y cuenta antes de autorizar.'))
            rec.sudo().write({'pago_estado':'autorizado'})
        return True

    def action_create_vendor_bill(self):
        self.ensure_one()
        self._check_accounting()
        self._ensure_finance_ready()
        if self.pago_estado != 'autorizado' or self.factura_id:
            raise UserError(_('El embarque no está listo para crear una factura.'))
        if self.cuenta_gasto_id.account_type not in ('expense','expense_direct_cost'):
            raise UserError(_('Configure una cuenta contable de gasto.'))
        bill = self.env['account.move'].with_company(self.company_id).create({
            'move_type':'in_invoice', 'partner_id':self.proveedor_id.id,
            'company_id':self.company_id.id, 'invoice_origin': self.name,
            'ref': 'TRANSPORTE/%s' % self.name,
            'invoice_line_ids': [(0,0,{'name':'Flete embarque %s (%s guías)' %
                (self.name,len(self.guia_ids)), 'quantity':1.0,
                'price_unit':self.valor_acordado,'account_id':self.cuenta_gasto_id.id})],
        })
        self.sudo().write({'factura_id':bill.id,'pago_estado':'facturado'})
        return {'type':'ir.actions.act_window','res_model':'account.move',
                'res_id':bill.id,'view_mode':'form','target':'current'}

    def action_verify_payment(self):
        self._check_accounting()
        for rec in self:
            if rec.pago_estado != 'facturado' or not rec.factura_id or rec.factura_id.state != 'posted' or rec.factura_id.payment_state != 'paid':
                raise UserError(_('Primero contabilice y pague completamente la factura del embarque.'))
            rec.sudo().write({'pago_estado':'pagado'})
        return True


class EmbarqueLiquidacionWizard(models.TransientModel):
    _name = 'transcash.embarque.liquidacion.wizard'
    _description = 'Asignar costo y cuenta al embarque'

    embarque_id = fields.Many2one('transcash.embarque', required=True, readonly=True)
    cuenta_gasto_id = fields.Many2one('account.account', required=True,
            domain="[('account_type','in',['expense','expense_direct_cost'])]")
    valor_acordado = fields.Float('Costo del viaje', required=True, digits=(16,2))

    def action_confirm(self):
        self.ensure_one()
        rec = self.embarque_id
        rec._check_accounting()
        if rec.pago_estado != 'pendiente' or self.valor_acordado <= 0:
            raise UserError(_('Costo positivo obligatorio y sin liquidación previa.'))
        if self.cuenta_gasto_id.account_type not in ('expense','expense_direct_cost'):
            raise UserError(_('Seleccione una cuenta de gasto.'))
        if ('company_ids' in self.cuenta_gasto_id._fields and
                rec.company_id not in self.cuenta_gasto_id.company_ids):
            raise UserError(_('La cuenta no pertenece a la compañía del embarque.'))
        rec.sudo().write({'valor_acordado':self.valor_acordado,'cuenta_gasto_id':self.cuenta_gasto_id.id})
        return {'type':'ir.actions.act_window_close'}
