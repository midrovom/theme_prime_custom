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
        ('embarque', 'En carga'),
        ('embarcada', 'Cargada'),
        ('ruta', 'En ruta'),
        ('destino', 'En destino'),
        ('revision', 'Entrega cerrada por chofer / revisión del cliente'),
        ('entregada', 'Recepción confirmada por cliente'),
        ('lista_pago', 'Lista para pago'),
        ('facturada', 'Factura proveedor creada'),
        ('pagada', 'Pagada'),
        ('cancelada', 'Cancelada'),
    ], default='registrada', required=True, tracking=True, index=True)

    embarque_id = fields.Many2one('transcash.embarque', string='Embarque / viaje', index=True, ondelete='restrict', copy=False, tracking=True)
    observacion_carga = fields.Text('Observación general de carga (legado)', copy=False)
    observacion_inicio_carga = fields.Text('Observación de inicio de carga', copy=False)
    observacion_fin_carga = fields.Text('Observación de fin de carga', copy=False)
    cierre_carga_autonomo = fields.Boolean('Carga cerrada con permiso autónomo', readonly=True, copy=False, default=False)
    cierre_carga_usuario_id = fields.Many2one('res.users', 'Chofer que cerró carga autónoma', readonly=True, copy=False)
    cierre_carga_fecha = fields.Datetime('Fecha de cierre autónomo', readonly=True, copy=False)
    tipo_documento = fields.Char('Tipo de documento transportado')
    numero_documento = fields.Char('Número de documento transportado')
    ruc_chofer = fields.Char('RUC / identificación del chofer')
    fecha_inicio_traslado = fields.Datetime('Inicio de traslado (ERP)')
    fecha_fin_traslado = fields.Datetime('Fin de traslado (ERP)')

    remitente_id = fields.Many2one('res.partner', string='Remitente')
    destinatario_id = fields.Many2one('res.partner', string='Destinatario', tracking=True)
    chofer_usuario_id = fields.Many2one('res.users', string='Usuario chofer', tracking=True)
    proveedor_id = fields.Many2one('res.partner', string='Proveedor a pagar', tracking=True)
    bodega_usuario_id = fields.Many2one('res.users', string='Responsable despacho')
    placa = fields.Char('Placa del vehículo')
    origen = fields.Char('Origen')
    destino = fields.Char('Destino')
    destino_codigo = fields.Char('Código de destino (ERP)', index=True)
    destino_ciudad = fields.Char('Ciudad de destino')
    destino_provincia = fields.Char('Provincia / región destino')

    numero_bultos = fields.Integer('Bultos')
    peso_kg = fields.Float('Peso (kg)')
    descripcion_carga = fields.Text('Descripción de mercancía')
    fecha_prevista = fields.Datetime('Llegada prevista')
    fecha_salida = fields.Datetime('Salida real', readonly=True, copy=False)
    fecha_llegada = fields.Datetime('Llegada real', readonly=True, copy=False)
    # La operación del chofer se cierra sin esperar la recepción del cliente.
    fecha_cierre_chofer = fields.Datetime('Entrega finalizada por chofer', readonly=True, copy=False, tracking=True)
    cierre_entrega_chofer_usuario_id = fields.Many2one('res.users', 'Cierre realizado por', readonly=True, copy=False)
    observacion_cierre_chofer = fields.Text('Observaciones de entrega del chofer', readonly=True, copy=False)
    persona_presente_chofer = fields.Char('Nombre de quien recibe (declarado por chofer)', readonly=True, copy=False)
    resultado_recepcion = fields.Selection([('pendiente','Pendiente de cliente'),
        ('conforme','Recibido conforme'), ('con_novedades','Recibido con novedades'),
        ('historica','Confirmada antes de V5.5')],
        string='Resultado de recepción del cliente', default='pendiente', readonly=True, copy=False, tracking=True)
    fecha_entrega = fields.Datetime('Recepción confirmada por cliente', readonly=True, copy=False)
    recibido_por = fields.Char('Nombre de quien recibe', readonly=True, copy=False)
    observacion_recepcion = fields.Text('Observación general de recepción', readonly=True, copy=False)
    confirmado_por_id = fields.Many2one('res.users', 'Confirmación por', readonly=True, copy=False)

    moneda_id = fields.Many2one('res.currency', string='Moneda', default=lambda self: self.env.company.currency_id)
    valor_acordado = fields.Monetary('Tarifa de transporte', currency_field='moneda_id',
                                    groups='logistica_transcash.group_logistica_manager,logistica_transcash.group_transcash_contabilidad')
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

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su:
            prohibited = {'embarque_id','aprobacion_global','incidencia_estado',
                          'fecha_salida','fecha_llegada','fecha_entrega','state',
                          'cierre_carga_autonomo','cierre_carga_usuario_id','cierre_carga_fecha',
                          'fecha_cierre_chofer','cierre_entrega_chofer_usuario_id',
                          'observacion_cierre_chofer','persona_presente_chofer','resultado_recepcion'}
            if any(prohibited.intersection(v) for v in vals_list):
                raise UserError(_('Los estados y el embarque se asignan mediante el flujo autorizado.'))
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.su and {'chofer_usuario_id','proveedor_id','placa'} & set(vals) and any(g.embarque_id for g in self):
            raise UserError(_('No cambie el chofer, transportista ni placa de una guía vinculada a embarque.'))
        if not self.env.su and 'embarque_id' in vals:
            raise UserError(_('Asigne o retire guías usando las acciones del embarque.'))
        if not self.env.su and {'observacion_carga','observacion_inicio_carga','observacion_fin_carga'} & set(vals):
            raise UserError(_('Las observaciones de carga se registran desde el embarque.'))
        # Los fletes de versiones anteriores son sólo históricos: el jefe de
        # Logística fija la tarifa exclusivamente en el embarque.
        if not self.env.su and 'valor_acordado' in vals:
            raise UserError(_('El valor del transporte se negocia en el embarque.'))
        # Un estado operativo no puede establecerse directamente vía interfaz o RPC.
        flow_fields = {'state','aprobacion_global','aprobacion_por_id','aprobacion_fecha',
                       'incidencia_estado','resolucion_por_id','confirmado_por_id',
                       'fecha_entrega','fecha_llegada','fecha_salida',
                       'cierre_carga_autonomo','cierre_carga_usuario_id','cierre_carga_fecha',
                          'fecha_cierre_chofer','cierre_entrega_chofer_usuario_id',
                          'observacion_cierre_chofer','persona_presente_chofer','resultado_recepcion'}
        if flow_fields & set(vals) and not self.env.su:

            raise UserError(_('Use las acciones del flujo para modificar el estado de la guía.'))
        return super().write(vals)

    def _check_internal_gallery_access(self):
        """Protege galería de backoffice, incluso cuando se llama por RPC."""
        self.ensure_one()
        user = self.env.user
        permitted = (user.has_group('logistica_transcash.group_transcash_consulta')
                     or user.has_group('logistica_transcash.group_logistica_bodega')
                     or user.has_group('logistica_transcash.group_transcash_operador_rutas'))
        if user.share or not permitted or self.company_id not in user.company_ids:
            from odoo.exceptions import AccessError
            raise AccessError(_('No dispone de acceso a esta galería.'))
        return True

    def action_open_evidence_gallery(self):
        self.ensure_one()
        self._check_internal_gallery_access()
        return {
            'type': 'ir.actions.act_url',
            'url': '/transcash/backoffice/guias/%d/galeria' % self.id,
            'target': 'new',
        }

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
            if guia.embarque_id:
                raise UserError(_('Inicie esta guía desde el embarque asignado.'))
            if guia.state != 'registrada':
                raise UserError(_('La guía debe estar registrada.'))
            guia.sudo().with_context(transcash_internal_flow=True).write({'state': 'embarque'})
            guia._track_event('Inicio de embarque')
        return True

    def action_depart(self):
        self._check_dispatcher()
        for guia in self:
            if guia.embarque_id:
                raise UserError(_('Autorice la salida desde el embarque completo.'))
            if guia.state != 'embarque':
                raise UserError(_('La guía debe estar en carga.'))
            cargas = guia.evidencia_ids.filtered(lambda e: e.tipo == 'carga')
            if not cargas or any(e.estado != 'aprobada' for e in cargas):
                raise UserError(_('Es obligatorio que bodega apruebe todas las evidencias de carga.'))
            if not guia.chofer_usuario_id:
                raise UserError(_('Asigne un usuario chofer antes de autorizar la salida.'))
            guia.sudo().with_context(transcash_internal_flow=True).write({'state': 'ruta', 'fecha_salida': fields.Datetime.now()})
            guia._track_event('Salida autorizada')
        return True

    def action_mark_loaded(self):
        """Terminar carga de una guía; el despacho debe haber aprobado la evidencia."""
        for guia in self:
            if not guia.embarque_id or guia.state != 'embarque':
                raise UserError(_('La guía debe estar en carga dentro de un embarque.'))
            user = self.env.user
            if not (user == guia.chofer_usuario_id and user.has_group('logistica_transcash.group_transcash_chofer')) and not self._is_manager():
                raise UserError(_('Solo el chofer de esta guía puede finalizar su carga.'))
            cargadas = guia.evidencia_ids.filtered(lambda e: e.tipo == 'carga')
            if not cargadas or not any(e.archivo for e in cargadas):
                raise UserError(_('Adjunte al menos una foto o video de carga sincronizado con el servidor antes de finalizar.'))
            driver_permission = self.env['transcash.chofer'].sudo().search([('usuario_id','=',user.id),
                ('activo','=',True), ('carga_autonoma','=',True)], limit=1)
            autonomous = bool(user == guia.chofer_usuario_id and
                user.has_group('logistica_transcash.group_transcash_chofer') and
                driver_permission and driver_permission.acceso_activado)
            if autonomous:
                if any(e.estado == 'objetada' for e in cargadas):
                    raise UserError(_('Una evidencia de carga está objetada por Bodega. Resuelva la objeción antes de finalizar.'))
                # No atribuir una aprobación falsa a Bodega. La evidencia sigue en estado
                # pendiente y la guía guarda el responsable y la hora de la excepción.
                guia.sudo().write({'state':'embarcada', 'cierre_carga_autonomo':True,
                    'cierre_carga_usuario_id':user.id,'cierre_carga_fecha':fields.Datetime.now()})
                guia._track_event('Carga cerrada por chofer con permiso autónomo',
                    'Sin aprobación previa de Bodega; evidencias originales conservadas')
            else:
                if any(e.estado != 'aprobada' for e in cargadas):
                    raise UserError(_('Bodega debe aprobar todas las evidencias de carga antes de finalizar.'))
                guia.sudo().write({'state':'embarcada'})
                guia._track_event('Guía cargada y evidencias aprobadas', guia.observacion_fin_carga or '')
        return True

    def action_arrive(self):
        for guia in self:
            if (guia.chofer_usuario_id != self.env.user or not self.env.user.has_group('logistica_transcash.group_transcash_chofer')) and not self._is_manager():
                raise UserError(_('Solo el chofer asignado puede registrar la llegada.'))
            if guia.state != 'ruta':
                raise UserError(_('La guía debe estar en ruta.'))
            guia.sudo().with_context(transcash_internal_flow=True).write({'state': 'destino', 'fecha_llegada': fields.Datetime.now()})
            guia._track_event('Llegada al destino')
        return True

    def action_close_driver_delivery(self, observation='', contact_name=''):
        """Cierre operativo, independiente de aprobación y reclamos del cliente.

        Una entrega físicamente cerrada libera el embarque SOLO cuando todas sus
        guías se cerraron; Contabilidad aún espera recepción, daños y NC.
        """
        self.ensure_one()
        for guia in self:
            user = self.env.user
            if guia.chofer_usuario_id != user or not user.has_group('logistica_transcash.group_transcash_chofer'):
                raise UserError(_('Solo el chofer asignado puede finalizar su entrega.'))
            # Serializar con crear otro viaje y cerrar las otras guías del mismo
            # embarque. El bloqueo se libera automáticamente al hacer commit.
            if guia.embarque_id:
                guia.embarque_id._lock_driver_operation(user.id)
            self.env.cr.execute('SELECT id FROM transcash_guia WHERE id = %s FOR UPDATE', (guia.id,))
            guia.invalidate_recordset(['state', 'fecha_llegada', 'fecha_cierre_chofer'])
            if guia.fecha_cierre_chofer:
                # Reintento HTTP después de perder señal: no crear otro cierre.
                return True
            if guia.state not in ('destino', 'revision'):
                raise UserError(_('Primero registre su llegada al destino.'))
            if not guia.fecha_llegada:
                raise UserError(_('Primero registre la llegada real al destino.'))
            fotos_descarga = guia.evidencia_ids.filtered(lambda e: e.tipo == 'llegada' and e.archivo)
            if not fotos_descarga:
                raise UserError(_('Suba y sincronice al menos una foto o video de descarga antes de finalizar. No necesita esperar la aprobación del cliente.'))
            # El nombre del receptor es obligatorio para cerrar la entrega,
            # pero se conserva como declaración del chofer, NO como conformidad.
            name = ' '.join((contact_name or '').split())
            if len(name) < 3 or not any(ch.isalpha() for ch in name):
                raise UserError(_('Escriba el nombre y apellido de la persona que recibió la mercadería.'))
            now = fields.Datetime.now()
            guia.sudo().write({
                'state': 'revision',
                'fecha_cierre_chofer': now,
                'cierre_entrega_chofer_usuario_id': user.id,
                'observacion_cierre_chofer': (observation or '').strip()[:4000],
                'persona_presente_chofer': name[:160],
            })
            guia._track_event('Chofer finalizó la entrega',
                'Receptor declarado por chofer: %s. %s' % (name[:160],
                 (observation or '').strip()[:600] or 'Sin novedades declaradas'))
            if guia.embarque_id:
                guia.embarque_id._refresh_delivered_state()
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

    def action_confirm_delivery(self, receiver_name, comment='', resultado='conforme'):
        """Recepción posterior e independiente del cierre del chofer.

        * Conforme: revisa en conjunto las evidencias pendientes de descarga.
        * Con novedades: deja el reclamo abierto, sin impedir otro viaje del chofer.
          Las roturas requieren su propio registro por producto con archivos.
        """
        for guia in self:
            if not guia._is_recipient() and not guia._is_manager():
                raise UserError(_('Solo el destinatario puede confirmar esta entrega.'))
            if guia.state != 'revision':
                raise UserError(_('La guía todavía no está pendiente de recepción del cliente.'))
            if resultado not in ('conforme', 'con_novedades'):
                raise UserError(_('Seleccione recepción conforme o con novedades.'))
            receiver_name = ' '.join((receiver_name or '').split())
            if len(receiver_name) < 3 or not any(ch.isalpha() for ch in receiver_name):
                raise UserError(_('Escriba el nombre completo de quien recibe.'))
            comment = (comment or '').strip()
            llegadas = guia.evidencia_ids.filtered(lambda e: e.tipo == 'llegada')
            if not llegadas:
                raise UserError(_('Todavía no hay evidencias de llegada para revisar.'))
            if resultado == 'conforme':
                if (guia.incidencia_estado == 'abierta' or
                    any(r.estado != 'rechazada' for r in guia.rotura_ids) or
                    any(e.estado == 'objetada' for e in llegadas) or
                    any(e.tipo == 'cliente' and e.tipo_novedad != 'ninguna'
                        for e in guia.evidencia_ids)):
                    raise UserError(_('La guía tiene reclamos o evidencias objetadas. Use «Recibí con novedades» para no perderlos.'))
            else:
                if len(comment) < 5:
                    raise UserError(_('Describa la novedad (mínimo cinco caracteres). Para roturas agregue producto, cantidad y evidencia.'))
                guia._open_incident('Novedad de recepción: %s' % comment[:250])
            # Un solo gesto revisa las fotos sin exigir una aprobación por archivo.
            # Una evidencia OBJETADA jamás se aprueba automáticamente.
            for evidencia in llegadas.filtered(lambda e: e.estado == 'pendiente'):
                evidencia.action_approve()
            guia.sudo().with_context(transcash_internal_flow=True).write({
                'state': 'entregada', 'fecha_entrega': fields.Datetime.now(),
                'recibido_por': receiver_name[:160],
                'observacion_recepcion': comment[:4000],
                'resultado_recepcion': resultado,
                'confirmado_por_id': self.env.user.id,
            })
            guia._track_event('Recepción confirmada por cliente' if resultado == 'conforme'
                else 'Cliente recibió con novedades',
                'Recibido por: %s. %s' % (receiver_name[:160], comment[:600]))
            if guia.embarque_id:
                guia.embarque_id._refresh_delivered_state()
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
        raise UserError(_('El flete se negocia por embarque en Logística. Las guías independientes históricas se conservan para consulta.'))

    def action_ready_payment(self):
        raise UserError(_('La aprobación financiera se realiza por embarque, no por guía.'))

    def action_create_vendor_bill(self):
        raise UserError(_('Transcash no emite facturas en Odoo Contabilidad. El proveedor adjunta su factura a la liquidación documental.'))

    def action_verify_payment(self):
        raise UserError(_('Los pagos se registran en Liquidaciones de transporte.'))

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
        item = dict(item)
        # Variaciones de nombres en ERPs externos sin cambiar el contrato principal.
        for alias, canonical in {
            'tipo_documento_transporte':'tipo_documento',
            'numero_documento_transporte':'numero_documento',
            'placa_vehiculo':'placa',
            'identificacion_chofer':'ruc_chofer',
        }.items():
            if alias in item and canonical not in item:
                item[canonical] = item[alias]
        guide_id = str(item.get('id_externo') or '').strip()
        number = str(item.get('numero_guia') or '').strip()
        if not guide_id or not number:
            raise ValidationError(_('id_externo y numero_guia son obligatorios.'))
        vals = {'external_id_erp': guide_id, 'name': number}
        for incoming, field in {
            'origen': 'origen', 'destino': 'destino', 'placa': 'placa',
            'direccion_origen': 'origen', 'direccion_destino': 'destino',
            'tipo_documento':'tipo_documento', 'numero_documento':'numero_documento',
            'ruc_chofer':'ruc_chofer',
            'descripcion_carga': 'descripcion_carga', 'estado_erp': 'estado_erp',
            'destino_codigo': 'destino_codigo', 'destino_ciudad':'destino_ciudad',
            'destino_provincia':'destino_provincia',
        }.items():
            if incoming in item:
                vals[field] = str(item[incoming] or '')[:500 if field == 'descripcion_carga' else 255]
        for incoming, field in {'bultos': 'numero_bultos', 'peso_kg': 'peso_kg',
}.items():
            if incoming in item and item[incoming] is not None:
                vals[field] = float(item[incoming]) if field != 'numero_bultos' else int(item[incoming])
        for api_field, db_field in [('fecha_inicio_traslado','fecha_inicio_traslado'),
                                    ('fecha_fin_traslado','fecha_fin_traslado')]:
            if api_field in item:
                if not item[api_field]:
                    vals[db_field] = False
                else:
                    try:
                        d = datetime.fromisoformat(str(item[api_field]).replace('Z','+00:00'))
                    except ValueError as exc:
                        raise ValidationError(_('Fecha inválida en %s') % api_field) from exc
                    if d.tzinfo is None:
                        raise ValidationError(_('%s debe incluir zona horaria.') % api_field)
                    vals[db_field] = d.astimezone(timezone.utc).replace(tzinfo=None)
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
        if 'empresa_transporte_codigo' in item and 'proveedor_codigo' not in item:
            partner = self._partner_by_ref(item['empresa_transporte_codigo'])
            if not partner:
                raise ValidationError(_('Empresa transportista no encontrada: %s') % item['empresa_transporte_codigo'])
            vals['proveedor_id'] = partner.id
        # El mismo POST /api/transcash/v1/guias homologa el destino antes de crear la guía.
        # No se exige una API adicional. Un código ya registrado nunca se renombra desde el ERP.
        if vals.get('destino_codigo'):
            destination = self.env['transcash.destino'].obtener_desde_erp(
                vals['destino_codigo'], vals.get('destino_ciudad'), vals.get('destino_provincia'),
                self.env.company.id)
            vals['destino_codigo'] = destination.codigo
            vals['destino_id'] = destination.id
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
            codigo = str(p.get('sku') or p.get('codigo') or '').strip()
            nombre = str(p.get('descripcion') or '').strip()
            unit = str(p.get('unidad') or '').lower().strip()
            aliases = {'m²':'m2', 'metros_cuadrados':'m2', 'metro_cuadrado':'m2', 'metros cuadrados':'m2',
                       'pallets':'pallet', 'und':'unidad', 'unid':'unidad', 'u':'unidad',
                       'cajas':'caja', 'metro':'metro', 'metros':'metro', 'm':'metro', 'kilos':'kg', 'kilogramos':'kg', 'unidades':'unidad'}
            unit = aliases.get(unit, unit)
            if not ext or ext in seen or not codigo or not nombre or unit not in ('m2','pallet','caja','kg','metro','unidad'):
                raise ValidationError(_('Producto sin ID único, código, descripción o unidad válida.'))
            seen.add(ext)
            try:
                qty = float(p.get('cantidad'))
                price = float(p.get('precio_unitario', 0) or 0)
                peso_linea = float(p.get('peso_kg',0) or 0)
                pallets = float(p.get('pallets', 0) or 0)
                cajas = float(p.get('cajas', 0) or 0)
            except (ValueError, TypeError):
                raise ValidationError(_('Cantidad o precio inválido en producto %s.') % codigo)
            import math
            if not all(math.isfinite(x) and 0 <= x < 1e10 for x in (price, peso_linea, pallets, cajas)) or not (math.isfinite(qty) and 0 < qty < 1e10):
                raise ValidationError(_('Cantidad o precio fuera de rango en %s.') % codigo)
            values = {'codigo':codigo[:128], 'producto':nombre[:255],
                      'cantidad':qty, 'unidad':unit, 'precio_unitario':price,
                      'peso_kg':peso_linea, 'pallets_info':pallets, 'cajas_info':cajas, 'vigente_erp':True,
                      'marca_codigo':str(p.get('marca_codigo') or '')[:128],
                      'marca_nombre':str(p.get('marca_nombre') or '')[:255],
                      'proveedor_producto_codigo':str(p.get('proveedor_producto_codigo') or '')[:128],
                      'proveedor_producto_nombre':str(p.get('proveedor_producto_nombre') or '')[:255]}
            old = Line.search([('guia_id','=',guia.id),('external_line_id','=',ext)], limit=1)
            if old:
                if old.rotura_ids and any(old[f] != values[f] for f in
                                        ('codigo','producto','cantidad','unidad','precio_unitario', 'peso_kg',
                                         'marca_codigo','marca_nombre',
                                         'proveedor_producto_codigo','proveedor_producto_nombre')):
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
                        # La asignación operativa de rutas (chofer/proveedor/placa)
                        # prevalece tras la confirmación de Logística: evitar que el
                        # cron ERP la modifique silenciosamente en una nueva importación.
                        if existing.embarque_id or existing.hoja_ruta_id:
                            for field in ('destino_id', 'destino_codigo', 'destino_ciudad',
                                          'destino_provincia', 'destino', 'chofer_usuario_id','proveedor_id','placa'):
                                vals.pop(field, None)
                        if existing.aprobacion_global == 'aprobada':
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
