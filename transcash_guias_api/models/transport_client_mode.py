# -*- coding: utf-8 -*-
"""Dos flujos de transporte sobre los modelos operativos de v5.32.

No declara un segundo modelo de viajes ni crea obligaciones contables para
transporte enviado por el cliente. Se preservan guías, rutas y evidencias.
"""
from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError

OPERATOR = 'logistica_transcash.group_transcash_operador_rutas'
MANAGER = 'logistica_transcash.group_logistica_manager'


class EmbarqueModalidad(models.Model):
    _inherit = 'transcash.embarque'

    modalidad_transporte = fields.Selection([
        ('contratado', 'Contratado por Transcash · con evidencias del chofer'),
        ('cliente', 'Enviado por el cliente · cierre por Logística'),
    ], string='Modalidad de transporte', default='contratado', required=True,
       readonly=True, copy=False, tracking=True, index=True,
       help='Transporte del cliente no origina flete, factura ni liquidación de transporte.')
    entregado_por_logistica_id = fields.Many2one('res.users', string='Entrega cerrada por Logística',
                                                readonly=True, copy=False)
    fecha_cierre_logistica = fields.Datetime('Fecha de cierre por Logística', readonly=True, copy=False)
    motivo_cierre_logistica = fields.Text('Constancia de entrega por Logística', readonly=True, copy=False)
    estado_aprobacion = fields.Selection(selection_add=[('no_aplica', 'No aplica · transporte del cliente')],
                                        ondelete={'no_aplica': 'set default'})
    estado_financiero = fields.Selection(selection_add=[('no_aplica', 'Sin flete · transporte del cliente')],
                                        ondelete={'no_aplica': 'set null'})

    def _check_operator_client(self):
        user = self.env.user
        if user.share or not (user.has_group(OPERATOR) or user.has_group(MANAGER)):
            raise AccessError(_('Solo un operador o jefe de Logística interno puede gestionar el transporte del cliente.'))
        if any(r.company_id not in user.company_ids for r in self):
            raise AccessError(_('La empresa del viaje no está autorizada.'))

    def write(self, vals):
        # El cambio de modalidad ocurre solamente desde una acción autorizada,
        # no por importación ERP o RPC directo. No depende de ocultar el campo.
        if 'modalidad_transporte' in vals and not self.env.context.get('tc_modalidad_autorizada'):
            raise AccessError(_('Cambie la modalidad desde la acción autorizada de Logística.'))
        next_mode = vals.get('modalidad_transporte')
        for trip in self:
            client = next_mode == 'cliente' or (next_mode is None and trip.modalidad_transporte == 'cliente')
            if client:
                if vals.get('estado_aprobacion') and vals['estado_aprobacion'] != 'no_aplica':
                    raise UserError(_('El transporte del cliente no puede aprobarse para pago.'))
                if 'valor_acordado' in vals and vals['valor_acordado']:
                    raise UserError(_('El transporte enviado por el cliente no genera valor a pagar.'))
        return super().write(vals)

    def action_set_client_transport(self):
        """Permite corregir un embarque nuevo SIN flete ni documentos vinculados."""
        self._check_operator_client()
        for trip in self.sorted('id'):
            self.env.cr.execute('SELECT id FROM transcash_embarque WHERE id=%s FOR UPDATE', (trip.id,))
            trip.invalidate_recordset(['state', 'estado_aprobacion', 'liquidacion_linea_id', 'valor_acordado'])
            if trip.modalidad_transporte == 'cliente':
                continue
            if (trip.state != 'preparacion' or trip.estado_aprobacion != 'pendiente' or
                    trip.liquidacion_linea_id or trip.valor_acordado):
                raise UserError(_('Solo puede cambiar a transporte del cliente en preparación, sin precio ni liquidación.'))
            trip.sudo().with_context(tc_modalidad_autorizada=True).write({
                'modalidad_transporte': 'cliente', 'estado_aprobacion': 'no_aplica',
                'valor_acordado': 0.0, 'tarifa_referencial_total': 0.0,
                'tarifa_id': False,
            })
            trip._message_log(body=_('Modalidad: transporte enviado por el cliente. Sin flete ni liquidación. Responsable: %s.') % self.env.user.name)
        return True

    def action_set_contracted_transport(self):
        self._check_operator_client()
        for trip in self.sorted('id'):
            self.env.cr.execute('SELECT id FROM transcash_embarque WHERE id=%s FOR UPDATE', (trip.id,))
            trip.invalidate_recordset(['state', 'estado_aprobacion', 'liquidacion_linea_id'])
            if trip.modalidad_transporte == 'contratado':
                continue
            if trip.state != 'preparacion' or trip.liquidacion_linea_id:
                raise UserError(_('Una modalidad ya despachada no puede convertirse en un flete pagable.'))
            trip.sudo().with_context(tc_modalidad_autorizada=True).write({
                'modalidad_transporte': 'contratado', 'estado_aprobacion': 'pendiente',
            })
            trip._message_log(body=_('Modalidad corregida antes del despacho: transporte contratado. Responsable: %s.') % self.env.user.name)
        return True

    @api.depends('estado_aprobacion', 'liquidacion_linea_id.liquidacion_id.estado', 'modalidad_transporte')
    def _compute_estado_financiero(self):
        super()._compute_estado_financiero()
        for trip in self:
            if trip.modalidad_transporte == 'cliente':
                trip.estado_financiero = 'no_aplica'

    @api.depends('guia_ids', 'guia_ids.state', 'guia_ids.fecha_cierre_chofer',
                 'guia_ids.fecha_cierre_logistica', 'modalidad_transporte')
    def _compute_guia_stats(self):
        super()._compute_guia_stats()
        for trip in self:
            if trip.modalidad_transporte == 'cliente':
                trip.guias_cerradas_chofer = len(trip.guia_ids.filtered(
                    lambda g: g.fecha_cierre_logistica or g.state in ('entregada','lista_pago','facturada','pagada')))

    def action_ready_for_driver(self):
        """Para transporte cliente, el despacho inicia el traslado sin una aceptación ficticia."""
        for trip in self.sorted('id'):
            if trip.modalidad_transporte != 'cliente':
                super(EmbarqueModalidad, trip).action_ready_for_driver()
                continue
            trip._check_operator_client()
            trip._lock_driver_operation(trip.chofer_usuario_id.id)
            self.env.cr.execute('SELECT id FROM transcash_embarque WHERE id=%s FOR UPDATE', (trip.id,))
            trip.invalidate_recordset(['state', 'ruta_ids', 'guia_ids', 'modalidad_transporte'])
            if trip.state != 'preparacion' or not trip.ruta_ids:
                raise UserError(_('El viaje debe tener rutas y estar en preparación.'))
            if any(r.state != 'cargada' or not r._has_carga_evidence() for r in trip.ruta_ids):
                raise UserError(_('Documente la carga con foto o video en cada hoja de ruta antes de despachar.'))
            if trip.objecion_pendiente or trip.observacion_rechazo:
                raise UserError(_('Resuelva primero las observaciones pendientes de carga.'))
            guias = trip.ruta_ids.mapped('guia_ids')
            if not guias or set(guias.ids) != set(trip.guia_ids.ids):
                raise UserError(_('Las guías deben coincidir con las rutas de este embarque.'))
            if any(g.state not in ('registrada', 'embarque', 'embarcada') for g in guias):
                raise UserError(_('Una guía ya salió o cambió de estado; recargue el viaje.'))
            now = fields.Datetime.now()
            guias.sudo().write({'state': 'ruta', 'fecha_salida': now})
            trip.sudo().write({'state': 'ruta', 'fecha_embarcado': now, 'fecha_salida': now})
            for guide in guias:
                guide._track_event('Carga documentada y despachada por Logística · transporte del cliente', publico_cliente=True)
            trip._message_log(body=_('Logística despachó el transporte del cliente. No requiere aceptación del chofer ni genera flete.'))
        return True

    def action_open_client_delivery_wizard(self):
        self.ensure_one()
        self._check_operator_client()
        if self.modalidad_transporte != 'cliente' or self.state != 'ruta':
            raise UserError(_('Solo puede cerrar por Logística un transporte del cliente que esté en traslado.'))
        return {
            'type': 'ir.actions.act_window', 'name': _('Registrar entrega por Logística'),
            'res_model': 'tc.transporte.cliente.cierre.wizard',
            'view_mode': 'form', 'target': 'new',
            'context': {'default_embarque_id': self.id},
        }

    def action_open_reprice_trip(self):
        self._forbid_client_freight()
        return super().action_open_reprice_trip()

    def action_close_client_delivery(self, reason):
        """Cierre OPERATIVO de Logística sin suplantar al chofer ni al cliente.

        Preserva la posibilidad de que el destinatario confirme con novedades.
        """
        self.ensure_one()
        self._check_operator_client()
        reason = ' '.join((reason or '').split())
        if len(reason) < 12 or len(reason) > 2000:
            raise ValidationError(_('Registre la constancia de entrega (12 a 2000 caracteres).'))
        self._lock_driver_operation(self.chofer_usuario_id.id)
        self.env.cr.execute('SELECT id FROM transcash_embarque WHERE id=%s FOR UPDATE', (self.id,))
        self.invalidate_recordset(['state','modalidad_transporte','guia_ids','ruta_ids'])
        if self.modalidad_transporte != 'cliente':
            raise AccessError(_('El transporte contratado requiere cierre del chofer.'))
        if self.state == 'entregado' and self.fecha_cierre_logistica:
            return True  # reintento HTTP seguro
        if self.state != 'ruta' or not self.guia_ids or not self.ruta_ids:
            raise UserError(_('Primero documente y despache todas las rutas del transporte del cliente.'))
        if any(r.embarque_id != self or not r._has_carga_evidence() for r in self.ruta_ids):
            raise UserError(_('Faltan rutas o evidencias de carga del viaje.'))
        if set(self.ruta_ids.mapped('guia_ids').ids) != set(self.guia_ids.ids):
            raise UserError(_('Las guías y rutas del embarque no coinciden.'))
        self.env.cr.execute('SELECT id FROM transcash_guia WHERE embarque_id=%s ORDER BY id FOR UPDATE', (self.id,))
        self.guia_ids.invalidate_recordset(['state', 'fecha_cierre_logistica'])
        if any(g.state not in ('ruta','destino','revision') or g.fecha_cierre_chofer for g in self.guia_ids):
            raise UserError(_('El estado de una guía no permite el cierre por Logística.'))
        now = fields.Datetime.now()
        self.guia_ids.sudo().write({
            'state': 'revision', 'fecha_llegada': now,
            'fecha_cierre_logistica': now,
            'cierre_logistica_usuario_id': self.env.user.id,
            'observacion_cierre_logistica': reason,
        })
        self.ruta_ids.sudo().write({'fecha_cierre_operativo': now})
        self.sudo().write({'state': 'entregado', 'fecha_entrega': now,
                           'fecha_cierre_logistica': now,
                           'entregado_por_logistica_id': self.env.user.id,
                           'motivo_cierre_logistica': reason})
        for guia in self.guia_ids:
            guia._track_event('Logística registró entrega · transporte enviado por el cliente',
                              'Responsable: %s. Constancia: %s' % (self.env.user.name, reason[:600]),
                              publico_cliente=True)
        self._message_log(body=_('Entrega registrada por Logística. Sin firma ni aceptación del chofer. Responsable: %s. Constancia: %s') %
                          (self.env.user.name, reason))
        return True

    def _forbid_client_freight(self):
        if any(r.modalidad_transporte == 'cliente' for r in self):
            raise UserError(_('El transporte del cliente no origina flete, factura ni liquidación.'))

    def action_configure_liquidation(self):
        self._forbid_client_freight()
        return super().action_configure_liquidation()

    def action_approve_transport(self):
        self._forbid_client_freight()
        return super().action_approve_transport()

    def action_open_exception_wizard(self):
        self._forbid_client_freight()
        return super().action_open_exception_wizard()

    def _approve_exception(self, reason):
        self._forbid_client_freight()
        return super()._approve_exception(reason)

    def action_accept_and_depart(self):
        self._forbid_client_driver()
        return super().action_accept_and_depart()

    def action_report_discrepancy(self, reason):
        self._forbid_client_driver()
        return super().action_report_discrepancy(reason)

    def action_begin_guide(self, guide_id, observacion=''):
        self._forbid_client_driver()
        return super().action_begin_guide(guide_id, observacion)

    def action_finish_guide(self, guide_id, observacion=''):
        self._forbid_client_driver()
        return super().action_finish_guide(guide_id, observacion)

    def action_mark_embarked(self):
        self._forbid_client_driver()
        return super().action_mark_embarked()

    def _forbid_client_driver(self):
        if any(r.modalidad_transporte == 'cliente' for r in self):
            raise AccessError(_('Este transporte es enviado por el cliente; no requiere acciones de chofer.'))


class RutaClientTransport(models.Model):
    _inherit = 'transcash.hoja.ruta'

    @api.depends('embarque_id.modalidad_transporte','guia_ids.fecha_cierre_logistica',
                 'guia_ids.fecha_cierre_chofer','guia_ids.state','guia_ids.embarque_id')
    def _compute_entrega_ruta(self):
        super()._compute_entrega_ruta()
        for route in self:
            if route.embarque_id.modalidad_transporte != 'cliente':
                continue
            guias = route.guia_ids.filtered(lambda g: g.embarque_id == route.embarque_id)
            cerradas = len(guias.filtered(lambda g: g.fecha_cierre_logistica or
                g.state in ('entregada','lista_pago','facturada','pagada')))
            route.guias_total = len(guias)
            route.guias_cerradas_chofer = cerradas
            route.estado_entrega = ('sin_guias' if not guias else 'completa' if cerradas == len(guias)
                                    else 'parcial' if cerradas else 'pendiente')


class GuiaClientTransport(models.Model):
    _inherit = 'transcash.guia'

    fecha_cierre_logistica = fields.Datetime('Entrega registrada por Logística', readonly=True, copy=False)
    cierre_logistica_usuario_id = fields.Many2one('res.users', 'Cerrada por Logística', readonly=True, copy=False)
    observacion_cierre_logistica = fields.Text('Constancia de entrega Logística', readonly=True, copy=False)

    def action_arrive(self):
        if any(g.embarque_id.modalidad_transporte == 'cliente' for g in self):
            raise AccessError(_('El transporte del cliente lo cierra Logística.'))
        return super().action_arrive()

    def action_close_driver_delivery(self, *args, **kwargs):
        if any(g.embarque_id.modalidad_transporte == 'cliente' for g in self):
            raise AccessError(_('No se requiere cierre del chofer en transporte del cliente.'))
        return super().action_close_driver_delivery(*args, **kwargs)

    def action_confirm_delivery(self, receiver_name, comment='', resultado='conforme'):
        # Evita exigir foto de DESCARGA del chofer inexistente en un viaje del
        # cliente. Mantiene la confirmación genuina, novedades y evidencia de carga.
        normal = self.filtered(lambda g: g.embarque_id.modalidad_transporte != 'cliente')
        if normal:
            super(GuiaClientTransport, normal).action_confirm_delivery(receiver_name, comment, resultado)
        for guia in (self - normal):
            if not guia._is_recipient() and not guia._is_manager():
                raise AccessError(_('Solo el destinatario puede confirmar la recepción.'))
            if guia.state != 'revision' or not guia.fecha_cierre_logistica:
                raise UserError(_('La guía aún no fue cerrada por Logística.'))
            if resultado not in ('conforme', 'con_novedades'):
                raise ValidationError(_('Seleccione un resultado válido.'))
            receptor = ' '.join((receiver_name or '').split())
            if len(receptor) < 3 or not any(c.isalpha() for c in receptor):
                raise ValidationError(_('Escriba el nombre de quien recibe.'))
            comment = (comment or '').strip()
            if resultado == 'conforme':
                if (guia.incidencia_estado == 'abierta' or any(r.estado != 'rechazada' for r in guia.rotura_ids)
                        or any(e.estado == 'objetada' for e in guia.evidencia_ids)
                        or any(e.tipo == 'cliente' and e.tipo_novedad != 'ninguna' for e in guia.evidencia_ids)):
                    raise UserError(_('Existen novedades: use recepción con novedades.'))
            else:
                if len(comment) < 5:
                    raise ValidationError(_('Describa la novedad de recepción.'))
                guia._open_incident('Novedad de recepción: %s' % comment[:250])
            if not guia.hoja_ruta_id or not guia.hoja_ruta_id._has_carga_evidence():
                raise UserError(_('Debe existir evidencia del embarque para confirmar la recepción.'))
            for ev in guia.evidencia_ids.filtered(lambda e: e.tipo == 'llegada' and e.estado == 'pendiente'):
                ev.action_approve()
            guia.sudo().write({
                'state': 'entregada', 'fecha_entrega': fields.Datetime.now(),
                'recibido_por': receptor[:160], 'observacion_recepcion': comment[:4000],
                'resultado_recepcion': resultado, 'confirmado_por_id': self.env.user.id,
            })
            guia._track_event('Recepción confirmada por cliente' if resultado == 'conforme'
                               else 'Recepción con novedades del cliente',
                               'Recibido por: %s. %s' % (receptor[:160], comment[:600]), publico_cliente=True)
        return True


class ArmarEmbarqueClientTransport(models.TransientModel):
    _inherit = 'transcash.armar.embarque.wizard'

    @api.model
    def _default_modalidad_transporte(self):
        existing_id = self.env.context.get('default_embarque_id')
        if existing_id:
            existing = self.env['transcash.embarque'].browse(int(existing_id)).exists()
            if existing:
                return existing.modalidad_transporte
        return self.env.context.get('tc_modalidad_transport_request', 'contratado')

    modalidad_transporte = fields.Selection([
        ('contratado', 'Contratado por Transcash'), ('cliente', 'Transporte enviado por cliente')],
        string='Modalidad de transporte', default=_default_modalidad_transporte,
        required=True)

    def action_confirm(self):
        self.ensure_one()
        if self.modalidad_transporte == 'contratado':
            if self.embarque_id and self.embarque_id.modalidad_transporte != 'contratado':
                raise UserError(_('Este embarque es transporte del cliente; no mezcle modalidades.'))
            return super().action_confirm()
        if self.modalidad_transporte != 'cliente':
            raise ValidationError(_('Seleccione una modalidad válida.'))
        if self.embarque_id and self.embarque_id.modalidad_transporte != 'cliente':
            raise UserError(_('No se pueden mezclar viajes contratados y transporte del cliente.'))
        # Reutiliza validaciones de permisos, destinos, locks y guías ya probadas
        # en v2.21; evita el tarifario incluso cuando crea el viaje un jefe.
        response = self._tc_operator_confirm_unpriced()
        trip = self.env['transcash.embarque'].browse(response['res_id'])
        if trip.modalidad_transporte != 'cliente':
            trip.action_set_client_transport()
        return response


class TarifaClientTransport(models.TransientModel):
    _inherit = 'transcash.tarifa.embarque.wizard'

    def action_confirm(self):
        if self.embarque_id.modalidad_transporte == 'cliente':
            raise UserError(_('El transporte del cliente no genera fletes.'))
        return super().action_confirm()


class ReprecioClientTransport(models.TransientModel):
    _inherit = 'transcash.corregir.tarifa.embarque.wizard'

    def action_confirm(self):
        if self.embarque_id.modalidad_transporte == 'cliente':
            raise UserError(_('El transporte del cliente no genera tarifas.'))
        return super().action_confirm()


class LiquidacionClientTransport(models.Model):
    _inherit = 'transcash.pago.liquidacion'

    @api.model
    def create_supplier_liquidation(self, ids):
        selected = [int(i) for i in ids]
        trips = self.env['transcash.embarque'].sudo().browse(selected).exists()
        if any(t.modalidad_transporte == 'cliente' for t in trips):
            raise AccessError(_('Los viajes enviados por clientes no pueden liquidarse.'))
        return super().create_supplier_liquidation(ids)


class LineaLiquidacionClientTransport(models.Model):
    _inherit = 'transcash.pago.liquidacion.linea'

    @api.model_create_multi
    def create(self, vals_list):
        ids = [v.get('embarque_id') for v in vals_list if v.get('embarque_id')]
        trips = self.env['transcash.embarque'].sudo().browse(ids).exists()
        if any(t.modalidad_transporte == 'cliente' for t in trips):
            raise AccessError(_('No puede incluir transporte del cliente en una liquidación.'))
        return super().create(vals_list)


class CierreEntregaClientWizard(models.TransientModel):
    _name = 'tc.transporte.cliente.cierre.wizard'
    _description = 'Constancia de entrega del transporte del cliente'

    embarque_id = fields.Many2one('transcash.embarque', required=True, readonly=True)
    constancia = fields.Text('Constancia de entrega', required=True)

    def action_confirm(self):
        self.ensure_one()
        self.embarque_id.action_close_client_delivery(self.constancia)
        return {'type': 'ir.actions.act_window_close'}
