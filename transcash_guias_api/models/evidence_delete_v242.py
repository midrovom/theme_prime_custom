# -*- coding: utf-8 -*-
"""Corrección controlada de evidencias de carga ANTES de aceptación del chofer.

La bitácora base es inmutable; este complemento permite eliminar un archivo
individual con auditoría y bloqueo transaccional, sin abrir permisos contables.
No afecta evidencias de entrega ni firmas de destinatarios.
"""
from odoo import models, _
from markupsafe import escape
from odoo.exceptions import AccessError, UserError


class RouteEvidenceCorrectionV242(models.Model):
    _inherit = 'transcash.hoja.ruta'

    def _tc_prepare_evidence_correction(self):
        """Bloqueo y autorización comunes para fotos nuevas y video heredado.

        El bloqueo por chofer/embarque evita borrar una foto mientras el chofer
        acepta el viaje en otra sesión. La política se revalida con locks activos.
        """
        self.ensure_one()
        self._check_operator()
        if self.company_id not in self.env.user.company_ids:
            raise AccessError(_('No puede corregir evidencias de otra compañía.'))
        trip = self.embarque_id
        if trip:
            trip._lock_driver_operation(trip.chofer_usuario_id.id)
            self.env.cr.execute('SELECT id FROM transcash_embarque WHERE id=%s FOR UPDATE', (trip.id,))
        self.env.cr.execute('SELECT id FROM transcash_hoja_ruta WHERE id=%s FOR UPDATE', (self.id,))
        self.invalidate_recordset(['embarque_id', 'state', 'guia_ids', 'fecha_cierre_operativo',
                                   'evidencia_carga_ids', 'video_carga', 'video_mime', 'fecha_video'])
        # No permitir una modificación silenciosa de la relación del viaje.
        if self.embarque_id != trip:
            raise UserError(_('La ruta cambió de embarque. Actualice la pantalla y vuelva a revisar.'))
        if self.state not in ('planificada', 'cargada') or self.fecha_cierre_operativo:
            raise UserError(_('Esta ruta ya no permite corregir evidencias de carga.'))
        if any(g.fecha_salida or g.fecha_cierre_chofer or g.fecha_cierre_logistica or
               g.state not in ('registrada', 'embarque', 'embarcada') for g in self.guia_ids):
            raise UserError(_('La ruta registra despachos o entregas; sus evidencias deben conservarse.'))
        if trip:
            trip.invalidate_recordset(['state', 'aceptado_chofer', 'fecha_aceptacion_chofer',
                                       'fecha_salida', 'fecha_entrega', 'fecha_cierre_logistica',
                                       'estado_aprobacion', 'aprobado_fecha', 'liquidacion_linea_id'])
            if (trip.state not in ('preparacion', 'embarcado') or trip.aceptado_chofer or
                    trip.fecha_aceptacion_chofer or trip.fecha_salida or trip.fecha_entrega or
                    trip.fecha_cierre_logistica):
                raise UserError(_('El chofer ya aceptó el viaje o comenzó la entrega. No se puede borrar evidencia.'))
            # Comprobación interna de liquidaciones: no otorgar al operador
            # lectura del maestro contable ni devolver importes en PWA.
            if (trip.estado_aprobacion not in ('pendiente', 'no_aplica') or
                    trip.aprobado_fecha or trip.sudo().liquidacion_linea_id or
                    trip.legado_liquidacion_bloqueada or
                    self.env['transcash.pago.liquidacion.linea'].sudo().search_count([
                        ('embarque_id', '=', trip.id)])):
                raise UserError(_('El viaje tiene gestiones financieras; la evidencia no puede eliminarse.'))
            if trip.state == 'embarcado':
                # Nunca cambiar un viaje enviado sin registrarlo en el flujo.
                # Esto también evita dejar al chofer un expediente sin fotografías.
                trip.action_reopen_packing()
                trip.invalidate_recordset(['state'])
                if trip.state != 'preparacion':
                    raise UserError(_('No se pudo devolver el viaje a preparación.'))
        return trip

    def _tc_refresh_after_evidence_correction(self):
        """Una ruta sin evidencia ACTUAL deja de estar lista para enviar."""
        self.ensure_one()
        self.invalidate_recordset(['evidencia_carga_ids', 'video_carga', 'video_mime',
                                   'fecha_video', 'state', 'cantidad_evidencias_carga'])
        if self.state == 'cargada' and not self._has_carga_evidence():
            self.sudo().write({'state': 'planificada'})

    def action_tc_delete_legacy_loading_video(self):
        """Eliminar el video legado (campo Binary), no las fotos de la bitácora."""
        self.ensure_one()
        with self.env.cr.savepoint():
            self._tc_prepare_evidence_correction()
            if not self.video_carga:
                raise UserError(_('El video ya fue eliminado. Actualice la pantalla.'))
            old_name = self.video_nombre or _('video histórico')
            self.sudo().write({'video_carga': False, 'video_nombre': False,
                               'video_mime': False, 'fecha_video': False,
                               'video_por_id': False})
            self._tc_refresh_after_evidence_correction()
            self.sudo()._message_log(body=_(
                'Video de carga eliminado antes de aceptación por %(user)s (ID %(uid)s). '
                'Archivo: %(name)s. La evidencia deberá registrarse nuevamente si hace falta.'
            ) % {'user': escape(self.env.user.name), 'uid': self.env.user.id, 'name': escape(old_name)})
        return True


class LoadingEvidenceDeleteV242(models.Model):
    _inherit = 'transcash.carga.evidencia.ruta'

    def unlink(self):
        """Excepción auditada a la inmutabilidad base, con validación ORM.

        Nunca se permite borrar simplemente pasando sudo() desde la PWA;
        se exige un usuario interno de Logística aun dentro de la ruta HTTP.
        """
        if not self:
            return True
        for evidence in self.sorted('id'):
            with self.env.cr.savepoint():
                route = evidence.ruta_id
                if not route:
                    raise UserError(_('La evidencia no tiene hoja de ruta válida.'))
                route._tc_prepare_evidence_correction()
                self.env.cr.execute(
                    'SELECT id FROM transcash_carga_evidencia_ruta WHERE id=%s FOR UPDATE',
                    (evidence.id,)
                )
                if not self.env.cr.fetchone():
                    raise UserError(_('La evidencia ya fue eliminada por otro usuario. Actualice la pantalla.'))
                evidence.invalidate_recordset(['ruta_id', 'nombre', 'tipo', 'fecha', 'usuario_id'])
                if evidence.ruta_id != route:
                    raise UserError(_('La evidencia cambió de ruta. Actualice la pantalla.'))
                file_name = evidence.nombre or _('archivo sin nombre')
                evidence_id = evidence.id
                kind = evidence.tipo
                created_by = evidence.usuario_id.name or ''
                created_at = str(evidence.fecha or '')
                # El modelo principal impide unlink en todos los casos.
                # Saltar solo ese veto después de los controles precedentes.
                models.Model.unlink(evidence.sudo())
                route._tc_refresh_after_evidence_correction()
                route.sudo()._message_log(body=_(
                    'Evidencia de carga eliminada por %(user)s (ID %(uid)s) antes de la '
                    'aceptación del chofer. Archivo: %(file)s (evidencia #%(id)s, tipo %(type)s, '
                    'subida por %(author)s el %(date)s).'
                ) % {'user': escape(self.env.user.name), 'uid': self.env.user.id,
                     'file': escape(file_name), 'id': evidence_id, 'type': escape(kind),
                     'author': escape(created_by), 'date': created_at})
        return True
