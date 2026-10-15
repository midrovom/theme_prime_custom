"""Comprobantes y revisiones con autorizaciones verificadas del lado servidor."""
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class Evidencia(models.Model):
    _name = 'transcash.evidencia'
    _description = 'Evidencia de transporte'
    _order = 'create_date desc'

    guia_id = fields.Many2one('transcash.guia', required=True, ondelete='cascade', index=True)
    tipo = fields.Selection([
        ('carga', 'Carga / embarque'),
        ('llegada', 'Arribo / descarga'),
        ('cliente', 'Observación del destinatario'),
        ('novedad', 'Novedad en tránsito'),
    ], required=True)
    observacion = fields.Text('Observación', required=True)
    archivo = fields.Binary('Foto o video', attachment=True, copy=False)
    rotura_id = fields.Many2one('transcash.rotura', string='Rotura relacionada', ondelete='restrict', index=True)
    archivo_nombre = fields.Char('Archivo')
    archivo_mime = fields.Char('Tipo archivo')
    autor_usuario_id = fields.Many2one('res.users', string='Registrado por', readonly=True)
    fecha_captura_dispositivo = fields.Char('Fecha informada por el teléfono', readonly=True)
    estado = fields.Selection([
        ('registrada', 'Registrada'), ('pendiente', 'Por aprobar'),
        ('aprobada', 'Aprobada'), ('objetada', 'Objetada'),
    ], required=True, default='pendiente', index=True)
    tipo_novedad = fields.Selection([
        ('ninguna', 'Sin novedad'), ('rotura', 'Rotura'),
        ('faltante', 'Faltante'), ('otro', 'Otra'),
    ], default='ninguna', required=True)
    revisado_por_id = fields.Many2one('res.users', string='Revisado por', readonly=True)
    fecha_revision = fields.Datetime('Fecha de revisión', readonly=True)
    motivo_objecion = fields.Text('Motivo de objeción', readonly=True)
    respuesta_chofer = fields.Text('Respuesta del chofer', readonly=True)
    fecha_respuesta = fields.Datetime('Fecha de respuesta', readonly=True)

    @api.model
    def register_evidence(self, guia, tipo, observacion, file_data, filename, mime, tipo_novedad='ninguna', rotura_id=False):
        """Usado exclusivamente por portal controlado; también valida permisos aquí."""
        user = self.env.user
        if guia.aprobacion_global == 'aprobada':
            raise UserError(_('La guía está aprobada y no admite nuevas evidencias.'))
        if tipo in ('carga', 'llegada', 'novedad'):
            # Vendedores registran exclusivamente medios asociados a la
            # rotura propia; NO pueden subir novedades operativas generales.
            seller_damage = bool(rotura_id and tipo == 'novedad' and guia._is_seller(user)
                                 and self.env['transcash.rotura'].sudo().browse(rotura_id).reportado_por_id == user)
            if not (guia.chofer_usuario_id == user and user.has_group('logistica_transcash.group_transcash_chofer')) and not seller_damage:
                raise UserError(_('Solo el chofer puede subir esta evidencia, salvo vendedor que documenta su propia rotura.'))
            allowed = {'carga': ('embarque',), 'llegada': ('destino', 'revision'),
                       'novedad': ('embarque', 'embarcada', 'ruta', 'destino', 'revision')}
            if guia.state not in allowed[tipo]:
                raise UserError(_('No puede registrar esta evidencia en el estado actual.'))
        elif tipo == 'cliente':
            if not guia._is_recipient(user):
                raise UserError(_('Solo el destinatario puede añadir observaciones de recepción.'))
            if guia.state not in ('destino', 'revision', 'entregada'):
                raise UserError(_('La recepción no está habilitada.'))
        else:
            raise UserError(_('Tipo de evidencia no permitido.'))
        if not (observacion or '').strip():
            raise UserError(_('Debe escribir una observación.'))
        if tipo in ('carga', 'llegada') and not file_data:
            raise UserError(_('Es obligatoria una foto o documento del embarque o llegada.'))
        if tipo_novedad == 'rotura' and not rotura_id:
            raise UserError(_('Seleccione producto, cantidad rota y evidencia en Registrar rotura.'))
        if rotura_id and not self.sudo().env['transcash.rotura'].browse(rotura_id).exists():
            raise UserError(_('Rotura inexistente.'))
        if rotura_id and self.sudo().env['transcash.rotura'].browse(rotura_id).guia_id != guia:
            raise UserError(_('La rotura no pertenece a esta guía.'))
        if tipo_novedad not in ('ninguna', 'rotura', 'faltante', 'otro'):
            raise UserError(_('La novedad no es válida.'))
        ev = self.sudo().create({
            'guia_id': guia.id, 'tipo': tipo, 'observacion': observacion[:4000],
            'archivo': file_data or False, 'archivo_nombre': filename or False,
            'archivo_mime': mime or False, 'autor_usuario_id': user.id,
            'estado': 'pendiente' if tipo in ('carga', 'llegada') else 'registrada',
            'tipo_novedad': tipo_novedad, 'rotura_id': rotura_id or False,
        })
        if tipo == 'llegada' and guia.state == 'destino':
            guia.sudo().with_context(transcash_internal_flow=True).write({'state': 'revision'})
        if tipo_novedad != 'ninguna' and not rotura_id:
            guia._open_incident('%s: %s' % (tipo_novedad, observacion[:250]))
        guia._track_event('Evidencia registrada', '%s / #%d' % (tipo, ev.id))
        return ev

    def write(self, vals):
        # The controller / authorized action is the only writer via validated sudo.
        # ACL or a custom RPC context must never allow rewriting historical media.
        if not self.env.su:
            raise UserError(_('Las evidencias y revisiones son inmutables; use las acciones del flujo.'))
        return super().write(vals)

    def action_open_object_wizard(self):
        self.ensure_one()
        if self.tipo != 'carga' or self.estado not in ('pendiente', 'aprobada'):
            raise UserError(_('Solo se puede objetar una carga pendiente o aprobada.'))
        self.guia_id._check_dispatcher()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Objetar evidencia de carga'),
            'res_model': 'transcash.object.wizard', 'view_mode': 'form',
            'target': 'new', 'context': {'default_evidencia_id': self.id},
        }

    def action_approve(self):
        """La aprobación de carga corresponde a bodega. La llegada, al receptor."""
        for ev in self:
            guia = ev.guia_id
            if ev.tipo == 'carga':
                guia._check_dispatcher()
                if guia.state != 'embarque' and not (guia.cierre_carga_autonomo and
                        guia.state in ('embarcada','ruta','destino','revision','entregada') and
                        guia.aprobacion_global != 'aprobada'):
                    raise UserError(_('Solo es posible revisar esta carga antes de aprobar la guía completa.'))
            elif ev.tipo == 'llegada':
                if not guia._is_recipient() and not guia._is_manager():
                    raise UserError(_('Solo el destinatario valida la evidencia de llegada.'))
                if guia.state != 'revision':
                    raise UserError(_('Solo se pueden aprobar evidencias durante la revisión.'))
            else:
                raise UserError(_('Esta evidencia no requiere aprobación.'))
            if ev.estado not in ('pendiente', 'objetada'):
                raise UserError(_('La evidencia no está pendiente de revisión.'))
            ev.sudo().write({
                'estado': 'aprobada', 'revisado_por_id': self.env.user.id,
                'fecha_revision': fields.Datetime.now(),
            })
            guia._track_event('Evidencia aprobada', '#%s' % ev.id)
        return True

    def object_evidence(self, reason):
        for ev in self:
            guia = ev.guia_id
            if ev.tipo == 'carga':
                guia._check_dispatcher()
                if guia.state != 'embarque' and not (guia.cierre_carga_autonomo and
                        guia.state in ('embarcada','ruta','destino','revision','entregada') and
                        guia.aprobacion_global != 'aprobada'):
                    raise UserError(_('La revisión de la evidencia ya está cerrada.'))
            elif ev.tipo == 'llegada':
                if not guia._is_recipient():
                    raise UserError(_('Solo el destinatario puede objetar la entrega.'))
                if guia.state != 'revision':
                    raise UserError(_('La revisión ya finalizó.'))
            else:
                raise UserError(_('Esta evidencia no admite objeciones.'))
            if ev.estado not in ('pendiente', 'aprobada'):
                raise UserError(_('La evidencia no admite una nueva objeción.'))
            reason = (reason or '').strip()
            if len(reason) < 5:
                raise UserError(_('Explique el motivo de la objeción (mínimo 5 caracteres).'))
            ev.sudo().write({
                'estado': 'objetada', 'motivo_objecion': reason[:4000],
                'revisado_por_id': self.env.user.id,
                'fecha_revision': fields.Datetime.now(),
            })
            guia._open_incident('Evidencia objetada #%s: %s' % (ev.id, reason[:250]))
        return True

    def answer_objection(self, reply):
        for ev in self:
            if (ev.guia_id.chofer_usuario_id != self.env.user or not self.env.user.has_group('logistica_transcash.group_transcash_chofer')) or ev.tipo != 'llegada':
                raise UserError(_('Solo el chofer puede responder a su evidencia de llegada.'))
            if ev.estado != 'objetada' or ev.guia_id.state != 'revision':
                raise UserError(_('La objeción no está abierta.'))
            reply = (reply or '').strip()
            if not reply:
                raise UserError(_('Escriba una respuesta.'))
            ev.sudo().write({'respuesta_chofer': reply[:4000], 'fecha_respuesta': fields.Datetime.now()})
            ev.guia_id._track_event('Respuesta del chofer', '#%s' % ev.id)
        return True
