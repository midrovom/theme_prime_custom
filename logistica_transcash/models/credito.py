"""Solicitud documental de nota de crédito al ERP emisor; no emite comprobantes fiscales."""
import json
import base64
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class SolicitudNotaCredito(models.Model):
    _name = 'transcash.nota.credito'
    _description = 'Solicitud de nota de crédito por roturas'
    _order = 'create_date desc'

    guia_id = fields.Many2one('transcash.guia', required=True, ondelete='restrict', index=True)
    company_id = fields.Many2one(related='guia_id.company_id', store=True)
    estado = fields.Selection([('borrador','Borrador de propuesta'),
                               ('propuesta','Pendiente de aprobación'),
                               ('rechazada_aprobacion','Devuelta por aprobador'),
                               ('aprobada','Aprobada para emisión'),
                               ('enviada','Enviada al ERP'),
                               ('emitida','Nota de crédito emitida'),
                               ('rechazada','Rechazada por ERP')],
                              default='borrador', index=True, required=True)
    linea_ids = fields.One2many('transcash.nota.credito.linea','solicitud_id', string='Productos reclamados')
    numero_erp = fields.Char('Número de nota de crédito (ERP)', copy=False)
    referencia_erp = fields.Char('Referencia de solicitud ERP', copy=False, readonly=True)
    observacion_erp = fields.Text('Respuesta ERP', copy=False, readonly=True)
    propuesta_por_id = fields.Many2one('res.users', readonly=True)
    propuesta_fecha = fields.Datetime(readonly=True)
    aprobada_por_id = fields.Many2one('res.users', readonly=True)
    aprobada_fecha = fields.Datetime(readonly=True)
    motivo_rechazo_aprobacion = fields.Text('Motivo del rechazo de la propuesta')
    archivo_nc = fields.Binary('Comprobante NC emitida (PDF/imagen)', attachment=True, copy=False)
    archivo_nc_nombre = fields.Char('Nombre del comprobante')
    documento_validado_por_id = fields.Many2one('res.users', string='Adjuntado y validado por', readonly=True)
    documento_validado_fecha = fields.Datetime(readonly=True)
    solicitada_fecha = fields.Datetime(readonly=True)
    confirmada_fecha = fields.Datetime(readonly=True)
    moneda_id = fields.Many2one(related='guia_id.moneda_id')
    monto_estimado = fields.Monetary(compute='_compute_monto', currency_field='moneda_id')

    _sql_constraints = [('solicitud_unica', 'unique(guia_id)', 'La guía ya tiene solicitud de nota de crédito.')]

    @api.depends('linea_ids.subtotal')
    def _compute_monto(self):
        for req in self:
            req.monto_estimado = sum(req.linea_ids.mapped('subtotal'))

    @api.model
    def prepare_from_guide(self, guia):
        if not self.env.user.has_group('logistica_transcash.group_transcash_ventas_admin'):
            raise UserError(_('Solo Administración de Ventas prepara propuestas.'))
        if guia.aprobacion_global != 'aprobada' or guia.state not in ('entregada','lista_pago','facturada','pagada'):
            raise UserError(_('Primero valide la entrega completa de la guía.'))
        damages = guia.rotura_ids.filtered(lambda r: r.estado == 'aprobada')
        if not damages or guia.rotura_ids.filtered(lambda r: r.estado == 'pendiente'):
            raise UserError(_('Deben existir roturas aprobadas y ninguna pendiente.'))
        existing = self.search([('guia_id', '=', guia.id)], limit=1)
        if existing:
            return existing
        grouped = {}
        for r in damages:
            grouped[r.linea_id.id] = grouped.get(r.linea_id.id, 0.0) + r.cantidad
        lines = [(0, 0, {'linea_guia_id':line_id, 'cantidad':qty,
                          'codigo':self.env['transcash.guia.linea'].browse(line_id).codigo,
                          'producto':self.env['transcash.guia.linea'].browse(line_id).producto,
                          'unidad':self.env['transcash.guia.linea'].browse(line_id).unidad,
                          'precio_unitario':self.env['transcash.guia.linea'].browse(line_id).precio_unitario})
                 for line_id, qty in grouped.items()]
        req = self.sudo().create({'guia_id':guia.id, 'linea_ids':lines})
        guia._track_event('Solicitud de nota de crédito preparada', 'NC #%d / %d productos' % (req.id,len(lines)), publico_cliente=False)
        return req

    def write(self, vals):
        # Solo Crédito y Cobranzas puede editar campos documentales; nunca el
        # estado, monto, líneas ni las aprobaciones directamente desde RPC.
        if not self.env.su:
            allowed = {'numero_erp','archivo_nc','archivo_nc_nombre'}
            if set(vals) == {'motivo_rechazo_aprobacion'} and self.env.user.has_group('logistica_transcash.group_transcash_nc_aprobador') and all(r.estado == 'propuesta' for r in self):
                return super().write(vals)
            if set(vals) - allowed or not self.env.user.has_group('logistica_transcash.group_transcash_cobranzas'):
                raise UserError(_('No tiene autorización para modificar esta solicitud.'))
            if any(r.estado not in ('enviada','emitida') for r in self):
                raise UserError(_('El documento solo puede cargarse tras solicitar la emisión.'))
            if any(r.documento_validado_por_id for r in self):
                raise UserError(_('El comprobante validado no puede reemplazarse.'))
        return super().write(vals)

    def action_propose(self):
        if not self.env.user.has_group('logistica_transcash.group_transcash_ventas_admin'):
            raise UserError(_('Solo el Administrador de Ventas propone notas de crédito.'))
        for rec in self:
            if rec.estado not in ('borrador','rechazada_aprobacion'):
                raise UserError(_('La propuesta no está disponible para envío a aprobación.'))
            if not rec.linea_ids or rec.guia_id.aprobacion_global != 'aprobada':
                raise UserError(_('Falta validar la guía y las cantidades dañadas.'))
            rec.sudo().write({'estado':'propuesta','propuesta_por_id':self.env.user.id,
                              'propuesta_fecha':fields.Datetime.now(), 'motivo_rechazo_aprobacion':False})
            rec.guia_id._track_event('Propuesta NC enviada a aprobación', publico_cliente=False)
        return True

    def action_approve_proposal(self):
        if not self.env.user.has_group('logistica_transcash.group_transcash_nc_aprobador'):
            raise UserError(_('Solo el aprobador de notas de crédito decide.'))
        for rec in self:
            if rec.estado != 'propuesta':
                raise UserError(_('La solicitud no está pendiente de aprobación.'))
            if rec.propuesta_por_id == self.env.user:
                raise UserError(_('La persona que propone no puede aprobar su propia solicitud.'))
            rec.sudo().write({'estado':'aprobada','aprobada_por_id':self.env.user.id,
                              'aprobada_fecha':fields.Datetime.now()})
            rec.guia_id._track_event('Propuesta NC aprobada', str(rec.id), publico_cliente=False)
        return True

    def action_reject_proposal(self):
        if not self.env.user.has_group('logistica_transcash.group_transcash_nc_aprobador'):
            raise UserError(_('Solo el aprobador puede devolver propuestas.'))
        for rec in self:
            if rec.estado != 'propuesta' or len((rec.motivo_rechazo_aprobacion or '').strip()) < 5:
                raise UserError(_('Indique un motivo de rechazo de al menos cinco caracteres.'))
            rec.sudo().write({'estado':'rechazada_aprobacion'})
            rec.guia_id._track_event('Propuesta NC devuelta', rec.motivo_rechazo_aprobacion[:240], publico_cliente=False)
        return True

    def action_retry(self):
        if not self.env.user.has_group('logistica_transcash.group_transcash_cobranzas'):
            raise UserError(_('Solo Crédito y Cobranzas puede reintentar.'))
        for req in self:
            if req.estado != 'rechazada':
                raise UserError(_('Solo puede reintentar solicitudes rechazadas.'))
            req.sudo().write({'estado':'aprobada', 'referencia_erp':False,
                       'observacion_erp':False, 'numero_erp':False,
                       'solicitada_fecha':False, 'confirmada_fecha':False})
            req.guia_id._track_event('Solicitud NC reabierta para reintento', publico_cliente=False)
        return True

    def action_send(self):
        self.ensure_one()
        if not self.env.user.has_group('logistica_transcash.group_transcash_cobranzas'):
            raise UserError(_('Solo Crédito y Cobranzas puede enviar al ERP.'))
        if self.estado != 'aprobada':
            raise UserError(_('Esta solicitud ya fue procesada.'))
        cfg = self.env['ir.config_parameter'].sudo()
        url = (cfg.get_param('logistica_transcash.credit_api_url') or '').strip()
        token = cfg.get_param('logistica_transcash.api_outbound_token') or ''
        parsed = urlparse(url)
        if parsed.scheme != 'https' or not parsed.hostname or not token or parsed.username or parsed.password:
            raise UserError(_('Configure URL HTTPS de notas de crédito y token saliente en Ajustes.'))
        payload = {'solicitud_id': self.id, 'id_externo': self.guia_id.external_id_erp,
                   'numero_guia': self.guia_id.name,
                   'cliente_codigo': self.guia_id.destinatario_id.ref or '',
                   'moneda': self.moneda_id.name,
                   'productos': [{'id_linea': l.linea_guia_id.external_line_id,
                                  'codigo':l.codigo, 'descripcion':l.producto,
                                  'cantidad_rota_aprobada':l.cantidad, 'unidad':l.unidad,
                                  'valor_unitario_referencia':l.precio_unitario,
                                  'roturas': [{'reporte_id':r.id, 'cantidad':r.cantidad,
                                               'observacion':r.observacion,
                                               'evidencias': [
                                                   {'id':e.id,
                                                    'ruta': '/api/transcash/v1/evidencias/%d/archivo' % e.id,
                                                    'tipo_mime':e.archivo_mime}
                                                   for e in r.evidencia_ids]}
                                              for r in self.guia_id.rotura_ids.filtered(
                                                  lambda r: r.estado == 'aprobada' and r.linea_id == l.linea_guia_id)]}
                                 for l in self.linea_ids]}
        req = Request(url, data=json.dumps(payload).encode('utf-8'), method='POST',
                      headers={'Authorization':'Bearer ' + token, 'Content-Type':'application/json',
                               'Accept':'application/json'})
        try:
            with urlopen(req, timeout=25) as resp:
                raw = resp.read(131073)
                if len(raw) > 131072:
                    raise UserError(_('Respuesta demasiado grande del ERP.'))
                data = json.loads(raw.decode('utf-8')) if raw else {}
        except (OSError, ValueError, HTTPError, URLError) as exc:
            raise UserError(_('La solicitud no fue confirmada por ERP: %s') % str(exc)[:220]) from exc
        if not isinstance(data, dict) or not data.get('referencia'):
            raise UserError(_('El ERP debe responder con referencia de recepción.'))
        self.sudo().write({'estado':'enviada','solicitada_fecha':fields.Datetime.now(),
                    'referencia_erp':str(data['referencia'])[:128]})
        self.guia_id._track_event('Nota de crédito solicitada al ERP', self.referencia_erp, publico_cliente=False)
        return True

    @api.model
    def confirm_from_erp(self, data):
        # Confirmación idempotente; solo desde endpoint M2M autenticado.
        if not self.env.context.get('transcash_erp_callback'):
            raise UserError(_('Solo se permite la confirmación desde la API autenticada.'))
        if not isinstance(data, dict):
            raise ValidationError(_('El cuerpo debe ser un objeto JSON.'))
        try:
            req_id = int(data.get('solicitud_id'))
        except (TypeError, ValueError):
            raise ValidationError(_('solicitud_id inválido.'))
        req = self.sudo().browse(req_id).exists()
        referencia = str(data.get('referencia') or '').strip()
        estado = str(data.get('estado') or '').strip()
        numero = str(data.get('numero_nota_credito') or '').strip()
        if not req or not referencia or referencia != req.referencia_erp:
            raise ValidationError(_('Solicitud o referencia ERP desconocida.'))
        if estado not in ('emitida','rechazada'):
            raise ValidationError(_('estado debe ser emitida o rechazada.'))
        if estado == 'emitida' and not numero:
            raise ValidationError(_('Indique el número de nota de crédito emitida.'))
        if req.estado == estado and (estado == 'rechazada' or req.numero_erp == numero):
            return {'ok':True, 'ya_procesada':True}
        if req.estado != 'enviada':
            raise ValidationError(_('No se puede cambiar una solicitud ya finalizada.'))
        req.sudo().write({'estado':estado, 'numero_erp':numero[:128] or False,
                   'observacion_erp':str(data.get('observacion') or '')[:2000],
                   'confirmada_fecha':fields.Datetime.now()})
        req.guia_id._track_event('Estado de nota de crédito confirmado', '%s / %s' % (estado, numero), publico_cliente=False)
        return {'ok':True}

    def action_mark_issued(self):
        """Si ERP emitió fuera de banda, comprobar número y comprobante real."""
        if not self.env.user.has_group('logistica_transcash.group_transcash_cobranzas'):
            raise UserError(_('Solo Crédito y Cobranzas puede registrar el documento emitido.'))
        for rec in self:
            if rec.estado not in ('enviada','emitida') or not (rec.numero_erp or '').strip():
                raise UserError(_('La solicitud debe enviarse y tener número de NC del ERP.'))
            if not rec.archivo_nc:
                raise UserError(_('Adjunte el PDF o la imagen del comprobante oficial.'))
            raw = base64.b64decode(rec.archivo_nc)
            if not raw or len(raw) > 12*1024*1024 or not (raw.startswith(b'%PDF-') or raw.startswith(b'\xff\xd8\xff') or raw.startswith(b'\x89PNG\r\n\x1a\n')):
                raise UserError(_('Adjunte un documento PDF, JPG o PNG auténtico de hasta 12 MB.'))
            if rec.documento_validado_por_id:
                raise UserError(_('El comprobante ya fue confirmado y no admite sustitución.'))
            rec.sudo().write({'estado':'emitida','confirmada_fecha':fields.Datetime.now(),
                              'documento_validado_por_id':self.env.user.id,
                              'documento_validado_fecha':fields.Datetime.now()})
            rec.guia_id._track_event('Comprobante NC archivado por Crédito y Cobranzas', rec.numero_erp, publico_cliente=False)
        return True


class SolicitudNotaCreditoLinea(models.Model):
    _name = 'transcash.nota.credito.linea'
    _description = 'Detalle aprobado para solicitud de nota de crédito'

    solicitud_id = fields.Many2one('transcash.nota.credito', required=True, ondelete='cascade')
    linea_guia_id = fields.Many2one('transcash.guia.linea', required=True, ondelete='restrict')
    codigo = fields.Char(required=True)
    producto = fields.Char(required=True)
    cantidad = fields.Float(digits=(16, 3), required=True)
    unidad = fields.Selection([('m2','m²'),('pallet','Pallets'),('caja','Cajas'),
                               ('kg','kg'),('unidad','Unidades')], required=True)
    precio_unitario = fields.Monetary(currency_field='moneda_id')
    moneda_id = fields.Many2one(related='solicitud_id.moneda_id')
    subtotal = fields.Monetary(compute='_compute_subtotal',currency_field='moneda_id')

    @api.depends('cantidad','precio_unitario')
    def _compute_subtotal(self):
        for r in self:
            r.subtotal = r.cantidad * r.precio_unitario
