"""Guías y flujo de entrega. El ERP externo es fuente de datos maestros,
pero las aprobaciones locales y los estados operativos nunca se pisan por sync.
"""
import json
import logging
from datetime import datetime, timezone
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class Guia(models.Model):
    _name = 'transcash.guia'
    _description = 'Guía logística Transcash'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'
    _order = 'create_date desc'

    name = fields.Char('Número de guía', required=True, tracking=True, index=True)
    external_id_erp = fields.Char('ID único en ERP', index=True, copy=False)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    state = fields.Selection([
        ('registrada', 'Registrada'),
        ('embarque', 'En embarque'),
        ('ruta', 'En ruta'),
        ('destino', 'En destino'),
        ('revision', 'Pendiente de recepción'),
        ('entregada', 'Entregada'),
        ('lista_pago', 'Lista para pago'),
        ('facturada', 'Factura proveedor creada'),
        ('pagada', 'Pagada'),
        ('cancelada', 'Cancelada'),
    ], default='registrada', required=True, tracking=True, index=True)

    remitente_id = fields.Many2one('res.partner', string='Remitente')
    destinatario_id = fields.Many2one('res.partner', string='Destinatario', tracking=True)
    chofer_usuario_id = fields.Many2one('res.users', string='Usuario chofer', tracking=True)
    proveedor_id = fields.Many2one('res.partner', string='Proveedor a pagar', tracking=True)
    bodega_usuario_id = fields.Many2one('res.users', string='Responsable despacho')
    placa = fields.Char('Placa del vehículo')
    origen = fields.Char('Origen')
    destino = fields.Char('Destino')
    numero_bultos = fields.Integer('Bultos')
    peso_kg = fields.Float('Peso (kg)')
    descripcion_carga = fields.Text('Descripción de mercancía')
    fecha_prevista = fields.Datetime('Llegada prevista')
    fecha_salida = fields.Datetime('Salida real', readonly=True, copy=False)
    fecha_llegada = fields.Datetime('Llegada real', readonly=True, copy=False)
    fecha_entrega = fields.Datetime('Entrega confirmada', readonly=True, copy=False)
    recibido_por = fields.Char('Nombre de quien recibe', readonly=True, copy=False)
    observacion_recepcion = fields.Text('Observación general de recepción', readonly=True, copy=False)
    confirmado_por_id = fields.Many2one('res.users', 'Confirmación por', readonly=True, copy=False)

    moneda_id = fields.Many2one('res.currency', string='Moneda', default=lambda self: self.env.company.currency_id)
    valor_acordado = fields.Monetary('Tarifa de transporte', currency_field='moneda_id',
                                    groups='logistica_transcash.group_logistica_manager,logistica_transcash.group_transcash_contabilidad')
    cuenta_gasto_id = fields.Many2one('account.account', string='Cuenta de gasto',
                                      domain="[('account_type','in',['expense','expense_direct_cost'])]",
                                      groups='logistica_transcash.group_logistica_manager,logistica_transcash.group_transcash_contabilidad')
    factura_id = fields.Many2one('account.move', string='Factura del proveedor', readonly=True,
                                 copy=False, groups='logistica_transcash.group_logistica_manager,logistica_transcash.group_transcash_contabilidad')
    incidencia_estado = fields.Selection([
        ('ninguna', 'Sin incidencia'), ('abierta', 'Abierta'), ('resuelta', 'Resuelta'),
    ], default='ninguna', tracking=True, required=True, copy=False)
    resolucion_incidencia = fields.Text('Resolución de incidencia', copy=False)
    resolucion_por_id = fields.Many2one('res.users', string='Resuelta por', readonly=True, copy=False)

    linea_ids = fields.One2many('transcash.guia.linea', 'guia_id', string='Productos de la guía')
    rotura_ids = fields.One2many('transcash.rotura', 'guia_id', string='Roturas por producto')
    nota_credito_id = fields.One2many('transcash.nota.credito', 'guia_id', string='Solicitud NC')
    aprobacion_global = fields.Selection([
        ('pendiente', 'Pendiente de aprobación total'), ('aprobada', 'Guía aprobada')],
        default='pendiente', required=True, tracking=True, copy=False)
    aprobacion_por_id = fields.Many2one('res.users', string='Aprobada por', readonly=True, copy=False)
    aprobacion_fecha = fields.Datetime('Aprobación total', readonly=True, copy=False)
    total_productos = fields.Integer(compute='_compute_damage_summary', string='Productos')
    roturas_pendientes = fields.Integer(compute='_compute_damage_summary', string='Reportes por revisar')
    roturas_aprobadas = fields.Integer(compute='_compute_damage_summary', string='Reportes aprobados')
    evidencia_ids = fields.One2many('transcash.evidencia', 'guia_id', string='Evidencias')

    @api.depends('linea_ids', 'rotura_ids.estado')
    def _compute_damage_summary(self):
        for guia in self:
            guia.total_productos = len(guia.linea_ids.filtered('vigente_erp'))
            guia.roturas_pendientes = len(guia.rotura_ids.filtered(lambda r: r.estado == 'pendiente'))
            guia.roturas_aprobadas = len(guia.rotura_ids.filtered(lambda r: r.estado == 'aprobada'))

    evento_ids = fields.One2many('transcash.evento', 'guia_id', string='Trazabilidad')
    estado_erp = fields.Char('Estado reportado por ERP', readonly=True)
    ultima_sync = fields.Datetime('Última sincronización', readonly=True)

    _sql_constraints = [
        ('external_company_unique', 'unique(external_id_erp,company_id)',
         'El ID externo ya está registrado para esta compañía.'),
        ('value_non_negative', 'CHECK (valor_acordado >= 0)', 'La tarifa no puede ser negativa.'),
    ]

    def write(self, vals):
        # Los importes y datos contables son exclusivos de Contabilidad. El
        # contexto de RPC no equivale a autorización y no salta estas reglas.
        if not self.env.su and {'valor_acordado', 'cuenta_gasto_id', 'factura_id'} & set(vals):
            if not self.env.user.has_group('logistica_transcash.group_transcash_contabilidad'):
                raise UserError(_('Solo Contabilidad puede modificar datos de liquidación.'))
        if not self.env.su and self.env.user.has_group('logistica_transcash.group_transcash_contabilidad') and not self._is_manager():
            if set(vals) - {'cuenta_gasto_id', 'valor_acordado'}:
                raise UserError(_('Contabilidad solo puede editar cuenta de gasto y tarifa antes de facturar.'))
            if any(g.factura_id for g in self):
                raise UserError(_('La tarifa del transporte no se modifica después de facturar.'))
        if not self.env.su and {'proveedor_id','valor_acordado','cuenta_gasto_id'} & set(vals):
            if any(g.factura_id for g in self):
                raise UserError(_('No puede cambiar proveedor, tarifa ni cuenta después de facturar.'))
        # Un estado operativo no puede establecerse directamente vía interfaz o RPC.
        flow_fields = {'state','aprobacion_global','aprobacion_por_id','aprobacion_fecha',
                       'incidencia_estado','resolucion_por_id','confirmado_por_id',
                       'fecha_entrega','fecha_llegada','fecha_salida', 'factura_id'}
        if flow_fields & set(vals) and not self.env.su:

            raise UserError(_('Use las acciones del flujo para modificar el estado de la guía.'))
        return super().write(vals)

    def _track_event(self, accion, detalle='', publico_cliente=True):
        for guia in self:
            self.env['transcash.evento'].sudo().create({
                'guia_id': guia.id,
                'usuario_id': self.env.user.id,
                'accion': accion,
                'detalle': detalle or '',
                'publico_cliente': publico_cliente,
            })

    def _is_manager(self):
        return self.env.user.has_group('logistica_transcash.group_logistica_manager')

    def _is_warehouse(self):
        return self._is_manager() or self.env.user.has_group('logistica_transcash.group_logistica_bodega')

    def _check_dispatcher(self):
        for guia in self:
            if not self._is_warehouse():
                raise UserError(_('Solo bodega o un administrador de logística puede hacer esto.'))
            if not self._is_manager() and guia.bodega_usuario_id != self.env.user:
                raise UserError(_('No está asignado como responsable del despacho de esta guía.'))

    def action_start_loading(self):
        self._check_dispatcher()
        for guia in self:
            if guia.state != 'registrada':
                raise UserError(_('La guía debe estar registrada.'))
            guia.sudo().with_context(transcash_internal_flow=True).write({'state': 'embarque'})
            guia._track_event('Inicio de embarque')
        return True

    def action_depart(self):
        self._check_dispatcher()
        for guia in self:
            if guia.state != 'embarque':
                raise UserError(_('La guía debe estar en embarque.'))
            cargas = guia.evidencia_ids.filtered(lambda e: e.tipo == 'carga')
            if not cargas or any(e.estado != 'aprobada' for e in cargas):
                raise UserError(_('Es obligatorio que bodega apruebe todas las evidencias de carga.'))
            if not guia.chofer_usuario_id:
                raise UserError(_('Asigne un usuario chofer antes de autorizar la salida.'))
            guia.sudo().with_context(transcash_internal_flow=True).write({'state': 'ruta', 'fecha_salida': fields.Datetime.now()})
            guia._track_event('Salida autorizada')
        return True

    def action_arrive(self):
        for guia in self:
            if guia.chofer_usuario_id != self.env.user and not self._is_manager():
                raise UserError(_('Solo el chofer asignado puede registrar la llegada.'))
            if guia.state != 'ruta':
                raise UserError(_('La guía debe estar en ruta.'))
            guia.sudo().with_context(transcash_internal_flow=True).write({'state': 'destino', 'fecha_llegada': fields.Datetime.now()})
            guia._track_event('Llegada al destino')
        return True

    def _is_seller(self, user=None):
        user = user or self.env.user
        return bool(user.has_group('logistica_transcash.group_transcash_vendedor') and
                    self.company_id in user.company_ids)

    def _is_recipient(self, user=None):
        self.ensure_one()
        user = user or self.env.user
        return bool(self.destinatario_id and user.partner_id and
                    self.destinatario_id.commercial_partner_id == user.partner_id.commercial_partner_id)

    def action_confirm_delivery(self, receiver_name, comment=''):
        for guia in self:
            if not guia._is_recipient() and not self._is_manager():
                raise UserError(_('Solo el destinatario puede confirmar esta entrega.'))
            if guia.state != 'revision':
                raise UserError(_('La guía debe estar pendiente de recepción.'))
            llegadas = guia.evidencia_ids.filtered(lambda e: e.tipo == 'llegada')
            if not llegadas or any(e.estado == 'pendiente' for e in llegadas):
                raise UserError(_('El destinatario debe revisar todas las evidencias de llegada.'))
            receiver_name = (receiver_name or '').strip()
            if not receiver_name:
                raise UserError(_('Indique el nombre de quien recibe.'))
            guia.sudo().with_context(transcash_internal_flow=True).write({
                'state': 'entregada', 'fecha_entrega': fields.Datetime.now(),
                'recibido_por': receiver_name[:160],
                'observacion_recepcion': (comment or '')[:4000],
                'confirmado_por_id': self.env.user.id,
            })
            guia._track_event('Entrega confirmada', 'Recibido por: %s' % receiver_name)
        return True

    def _open_incident(self, detail):
        for guia in self:
            if guia.incidencia_estado != 'abierta':
                guia.sudo().write({'incidencia_estado': 'abierta'})
            guia._track_event('Incidencia', detail[:1000])

    def action_resolve_incident(self):
        if not self._is_manager():
            raise UserError(_('Solo el administrador puede resolver incidencias.'))
        for guia in self:
            if guia.incidencia_estado != 'abierta':
                raise UserError(_('No hay incidencia abierta.'))
            if not (guia.resolucion_incidencia or '').strip():
                raise UserError(_('Escriba la resolución antes de cerrar la incidencia.'))
            guia.sudo().write({'incidencia_estado': 'resuelta', 'resolucion_por_id': self.env.user.id})
            guia._track_event('Incidencia resuelta', guia.resolucion_incidencia[:1000])
        return True

    def action_approve_whole_guide(self):
        """Segunda validación: línea a línea y cierre global de la recepción."""
        if not self._is_manager():
            raise UserError(_('Solo administración puede validar la guía completa.'))
        for guia in self:
            if guia.state != 'entregada' or guia.aprobacion_global != 'pendiente':
                raise UserError(_('La entrega debe estar confirmada y aún sin aprobar.'))
            if not guia.linea_ids.filtered('vigente_erp'):
                raise UserError(_('No existe detalle de productos de ERP.'))
            if guia.roturas_pendientes:
                raise UserError(_('Revise y apruebe o rechace todas las roturas por producto.'))
            arrivals = guia.evidencia_ids.filtered(lambda e: e.tipo == 'llegada')
            if not arrivals or any(e.estado != 'aprobada' for e in arrivals):
                raise UserError(_('Las evidencias de llegada deben estar aprobadas y sin objeciones.'))
            guia.sudo().write({'aprobacion_global': 'aprobada',
                        'aprobacion_por_id': self.env.user.id,
                        'aprobacion_fecha': fields.Datetime.now()})
            guia._track_event('Guía aprobada en su totalidad',
                              '%d reporte(s) de roturas aprobadas' % guia.roturas_aprobadas)
        return True

    def action_prepare_credit_request(self):
        self.ensure_one()
        request = self.env['transcash.nota.credito'].prepare_from_guide(self)
        return {'type':'ir.actions.act_window', 'res_model':'transcash.nota.credito',
                'res_id':request.id, 'view_mode':'form', 'target':'current'}

    def action_configure_liquidation(self):
        self.ensure_one()
        if not self.env.user.has_group('logistica_transcash.group_transcash_contabilidad'):
            raise UserError(_('Solo Contabilidad puede configurar la liquidación.'))
        if self.factura_id or self.state not in ('entregada', 'lista_pago'):
            raise UserError(_('No puede modificar datos de una guía ya facturada o no entregada.'))
        return {'type':'ir.actions.act_window', 'name': _('Configurar liquidación'),
                'res_model': 'transcash.liquidacion.wizard', 'view_mode':'form',
                'target':'new', 'context': {'default_guia_id':self.id,
                                           'default_cuenta_gasto_id':self.cuenta_gasto_id.id or False,
                                           'default_valor_acordado':self.valor_acordado}}

    def action_ready_payment(self):
        if not self.env.user.has_group('logistica_transcash.group_transcash_contabilidad'):
            raise UserError(_('Solo el administrador puede autorizar la liquidación.'))
        for guia in self:
            if guia.state != 'entregada':
                raise UserError(_('La guía debe estar entregada.'))
            if guia.aprobacion_global != 'aprobada':
                raise UserError(_('Primero apruebe el total de la guía.'))
            if guia.roturas_pendientes:
                raise UserError(_('Existen roturas pendientes de revisión.'))
            if guia.roturas_aprobadas and (not guia.nota_credito_id or
                    guia.nota_credito_id[0].estado != 'emitida' or
                    not guia.nota_credito_id[0].documento_validado_por_id):
                raise UserError(_('Primero confirme la nota de crédito por las roturas aprobadas.'))
            if guia.incidencia_estado == 'abierta':
                raise UserError(_('Resuelva la incidencia antes de autorizar el pago.'))
            if not guia.proveedor_id:
                raise UserError(_('Falta el proveedor de transporte.'))
            guia.sudo().write({'state': 'lista_pago'})
            guia._track_event('Autorizada para liquidación', publico_cliente=False)
        return True

    def action_create_vendor_bill(self):
        if not self.env.user.has_group('logistica_transcash.group_transcash_contabilidad'):
            raise UserError(_('Solo el administrador puede generar la factura del proveedor.'))
        self.ensure_one()
        if self.state != 'lista_pago' or self.factura_id:
            raise UserError(_('La guía debe estar lista para pago y sin factura previa.'))
        if not self.proveedor_id or not self.cuenta_gasto_id:
            raise UserError(_('Configure el proveedor y la cuenta contable de gasto.'))
        if self.valor_acordado <= 0:
            raise UserError(_('La tarifa acordada debe ser mayor que cero.'))
        if self.moneda_id != self.company_id.currency_id:
            raise UserError(_('Este MVP exige la misma moneda de la compañía; no convierte divisas.'))
        bill = self.env['account.move'].with_company(self.company_id).create({
            'move_type': 'in_invoice',
            'partner_id': self.proveedor_id.id,
            'company_id': self.company_id.id,
            'invoice_origin': self.name,
            'ref': 'TRANSPORTE/%s' % self.name,
            'invoice_line_ids': [(0, 0, {
                'name': 'Flete de guía %s' % self.name,
                'quantity': 1.0,
                'price_unit': self.valor_acordado,
                'account_id': self.cuenta_gasto_id.id,
            })],
        })
        self.sudo().write({'factura_id': bill.id, 'state': 'facturada'})
        self._track_event('Factura del proveedor creada', bill.name or str(bill.id), publico_cliente=False)
        return {
            'type': 'ir.actions.act_window', 'res_model': 'account.move',
            'res_id': bill.id, 'view_mode': 'form', 'target': 'current',
        }

    def action_verify_payment(self):
        if not self.env.user.has_group('logistica_transcash.group_transcash_contabilidad'):
            raise UserError(_('Solo el administrador puede verificar pagos.'))
        for guia in self:
            if guia.state != 'facturada' or not guia.factura_id:
                raise UserError(_('La guía no tiene factura de proveedor asociada.'))
            if guia.factura_id.state != 'posted' or guia.factura_id.payment_state != 'paid':
                raise UserError(_('La factura debe estar contabilizada y completamente pagada.'))
            guia.sudo().write({'state': 'pagada'})
            guia._track_event('Pago verificado', publico_cliente=False)
        return True

    @api.model
    def _partner_by_ref(self, code):
        if not code:
            return False
        # El código externo debe estar cargado previamente en res.partner.ref.
        return self.env['res.partner'].sudo().search([('ref', '=', str(code))], limit=1)

    @api.model
    def _external_values(self, item):
        if not isinstance(item, dict):
            raise ValidationError(_('Cada guía debe ser un objeto JSON.'))
        guide_id = str(item.get('id_externo') or '').strip()
        number = str(item.get('numero_guia') or '').strip()
        if not guide_id or not number:
            raise ValidationError(_('id_externo y numero_guia son obligatorios.'))
        vals = {'external_id_erp': guide_id, 'name': number}
        for incoming, field in {
            'origen': 'origen', 'destino': 'destino', 'placa': 'placa',
            'descripcion_carga': 'descripcion_carga', 'estado_erp': 'estado_erp',
        }.items():
            if incoming in item:
                vals[field] = str(item[incoming] or '')[:500 if field == 'descripcion_carga' else 255]
        for incoming, field in {'bultos': 'numero_bultos', 'peso_kg': 'peso_kg',
                                'valor_acordado': 'valor_acordado'}.items():
            if incoming in item and item[incoming] is not None:
                vals[field] = float(item[incoming]) if field != 'numero_bultos' else int(item[incoming])
        if 'fecha_prevista' in item and item['fecha_prevista']:
            dt = datetime.fromisoformat(item['fecha_prevista'].replace('Z', '+00:00'))
            if dt.tzinfo is None:
                # El ERP debe proveer timezone para evitar ambigüedad.
                raise ValidationError(_('fecha_prevista debe incluir zona horaria.'))
            vals['fecha_prevista'] = dt.astimezone(timezone.utc).replace(tzinfo=None)
        for incoming, field in {
            'remitente_codigo': 'remitente_id', 'destinatario_codigo': 'destinatario_id',
            'proveedor_codigo': 'proveedor_id',
        }.items():
            if incoming in item:
                if not item[incoming]:
                    vals[field] = False
                else:
                    partner = self._partner_by_ref(item[incoming])
                    if not partner:
                        raise ValidationError(_('El código %s=%s no existe en Contactos (Referencia interna).') %
                                              (incoming, item[incoming]))
                    vals[field] = partner.id
        if 'chofer_login' in item:
            if not item['chofer_login']:
                vals['chofer_usuario_id'] = False
            else:
                user = self.env['res.users'].sudo().search([('login', '=', item['chofer_login'])], limit=1)
                if not user:
                    raise ValidationError(_('No existe el usuario chofer: %s') % item['chofer_login'])
                vals['chofer_usuario_id'] = user.id
        # Detalles de la guía no se incrustan en vals: reconciliación por ID de línea ERP.
        vals['ultima_sync'] = fields.Datetime.now()
        return vals

    @api.model
    def _sync_detail(self, guia, item):
        if 'productos' not in item:
            return  # No borra ni altera líneas si el ERP no las envía.
        products = item['productos']
        if not isinstance(products, list) or len(products) > 300:
            raise ValidationError(_('productos debe ser una lista de hasta 300 renglones.'))
        seen = set()
        Line = self.env['transcash.guia.linea'].sudo()
        for p in products:
            if not isinstance(p, dict):
                raise ValidationError(_('Cada producto debe ser objeto JSON.'))
            ext = str(p.get('id_linea') or '').strip()
            codigo = str(p.get('codigo') or '').strip()
            nombre = str(p.get('descripcion') or '').strip()
            unit = str(p.get('unidad') or '').lower().strip()
            aliases = {'m²':'m2', 'metros_cuadrados':'m2', 'pallets':'pallet',
                       'cajas':'caja', 'kilos':'kg', 'kilogramos':'kg', 'unidades':'unidad'}
            unit = aliases.get(unit, unit)
            if not ext or ext in seen or not codigo or not nombre or unit not in ('m2','pallet','caja','kg','unidad'):
                raise ValidationError(_('Producto sin ID único, código, descripción o unidad válida.'))
            seen.add(ext)
            try:
                qty = float(p.get('cantidad'))
                price = float(p.get('precio_unitario', 0) or 0)
            except (ValueError, TypeError):
                raise ValidationError(_('Cantidad o precio inválido en producto %s.') % codigo)
            if not (0 < qty < 1e10) or not (0 <= price < 1e10):
                raise ValidationError(_('Cantidad o precio fuera de rango en %s.') % codigo)
            values = {'codigo':codigo[:128], 'producto':nombre[:255],
                      'cantidad':qty, 'unidad':unit, 'precio_unitario':price, 'vigente_erp':True}
            old = Line.search([('guia_id','=',guia.id),('external_line_id','=',ext)], limit=1)
            if old:
                if old.rotura_ids and any(old[f] != values[f] for f in
                                        ('codigo','producto','cantidad','unidad','precio_unitario')):
                    raise ValidationError(_('La línea %s tiene roturas; no se permite cambiar su contenido.') % ext)
                if guia.aprobacion_global == 'aprobada' and any(old[f] != values[f] for f in values):
                    raise ValidationError(_('La guía ya está aprobada; productos bloqueados.'))
                old.write(values)
            else:
                if guia.aprobacion_global == 'aprobada':
                    raise ValidationError(_('No se puede agregar productos a una guía aprobada.'))
                Line.create(dict(values, guia_id=guia.id, external_line_id=ext))
        missing = Line.search([('guia_id','=',guia.id),('external_line_id','not in',list(seen))])
        for line in missing:
            if line.rotura_ids or guia.aprobacion_global == 'aprobada':
                raise ValidationError(_('No puede retirar la línea %s: tiene roturas o la guía está aprobada.') % line.external_line_id)
            line.write({'vigente_erp': False})

    @api.model
    def sync_payload(self, payload):
        """Idempotente por (company_id, id_externo), no importa estados locales."""
        if isinstance(payload, dict):
            items = payload.get('guias', [])
        elif isinstance(payload, list):
            items = payload
        else:
            raise ValidationError(_('JSON debe ser lista o un objeto con clave guias.'))
        if not isinstance(items, list) or len(items) > 500:
            raise ValidationError(_('La petición acepta hasta 500 guías por lote.'))
        result = {'creadas': 0, 'actualizadas': 0, 'errores': []}
        for i, item in enumerate(items):
            try:
                with self.env.cr.savepoint():
                    vals = self._external_values(item)
                    existing = self.sudo().search([
                        ('external_id_erp', '=', vals['external_id_erp']),
                        ('company_id', '=', self.env.company.id),
                    ], limit=1)
                    if existing:
                        # No sobrescribe valor luego de emitir factura ni campos internos.
                        if existing.factura_id or existing.aprobacion_global == 'aprobada':
                            vals.pop('valor_acordado', None)
                            vals.pop('proveedor_id', None)
                        existing.write(vals)
                        self._sync_detail(existing, item)
                        result['actualizadas'] += 1
                    else:
                        vals['company_id'] = self.env.company.id
                        guia = self.sudo().create(vals)
                        self._sync_detail(guia, item)
                        guia._track_event('Importada del ERP')
                        result['creadas'] += 1
            except Exception as exc:
                _logger.warning('Fallo en guía del lote %s: %s', i, exc)
                result['errores'].append({'indice': i, 'detalle': str(exc)[:250]})
        return result

    @api.model
    def action_sync_now(self):
        if not self._is_manager() and not self.env.is_superuser():
            raise UserError(_('Solo el administrador puede sincronizar guías.'))
        cfg = self.env['ir.config_parameter'].sudo()
        url = (cfg.get_param('logistica_transcash.api_url') or '').strip()
        token = cfg.get_param('logistica_transcash.api_outbound_token') or ''
        parsed = urlparse(url)
        if parsed.scheme != 'https' or not parsed.hostname:
            raise UserError(_('Configure una URL HTTPS válida del ERP en Ajustes.'))
        headers = {'Accept': 'application/json', 'User-Agent': 'Odoo-Transcash/18'}
        if token:
            headers['Authorization'] = 'Bearer ' + token
        try:
            req = Request(url, headers=headers, method='GET')
            with urlopen(req, timeout=25) as response:
                payload = response.read(5 * 1024 * 1024 + 1)
                if len(payload) > 5 * 1024 * 1024:
                    raise UserError(_('Respuesta ERP demasiado grande.'))
            result = self.sync_payload(json.loads(payload.decode('utf-8')))
        except (OSError, ValueError) as exc:
            raise UserError(_('No fue posible sincronizar con ERP: %s') % str(exc)[:250]) from exc
        cfg.set_param('logistica_transcash.last_sync', fields.Datetime.now())
        return {
            'type': 'ir.actions.client', 'tag': 'display_notification',
            'params': {
                'title': _('Sincronización ERP'),
                'message': _('Creadas: %(c)s; actualizadas: %(u)s; errores: %(e)s') % {
                    'c': result['creadas'], 'u': result['actualizadas'], 'e': len(result['errores']),
                },
                'type': 'warning' if result['errores'] else 'success', 'sticky': bool(result['errores']),
            },
        }

    @api.model
    def cron_sync_erp(self):
        cfg = self.env['ir.config_parameter'].sudo()
        if not cfg.get_param('logistica_transcash.api_url'):
            return
        try:
            self.action_sync_now()
        except Exception:
            _logger.exception('No se pudo sincronizar guías desde ERP')


class GuiaEvento(models.Model):
    _name = 'transcash.evento'
    _description = 'Evento de trazabilidad de guía'
    _order = 'create_date desc,id desc'

    guia_id = fields.Many2one('transcash.guia', required=True, ondelete='cascade', index=True)
    usuario_id = fields.Many2one('res.users', string='Realizado por', readonly=True)
    accion = fields.Char('Acción', required=True, readonly=True)
    detalle = fields.Text('Detalle', readonly=True)
    publico_cliente = fields.Boolean('Visible para destinatario', default=True, readonly=True)
    create_date = fields.Datetime('Fecha/hora', readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        # Solo operaciones de logística realizan altas; no se expone a usuarios del portal.
        return super().create(vals_list)

    def write(self, vals):
        raise UserError(_('La bitácora es inmutable.'))

    def unlink(self):
        raise UserError(_('No se puede borrar la bitácora.'))
