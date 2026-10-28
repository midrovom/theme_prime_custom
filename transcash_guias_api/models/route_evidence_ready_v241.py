# -*- coding: utf-8 -*-
"""Conciliar el estado de ruta y la evidencia REAL antes de liberar un viaje.

El método original action_reopen_packing() vuelve TODAS las rutas a
'planificada', incluso cuando sus fotos siguen siendo válidas. Esta extensión
restaura 'cargada' exclusivamente si _has_carga_evidence() lo permite.
No convierte evidencia histórica de una carga modificada en evidencia válida.
"""
from odoo import models, _
from odoo.exceptions import AccessError, UserError


class TranscashTripEvidenceReadyV241(models.Model):
    _inherit = 'transcash.embarque'

    def _tc_restore_valid_route_evidence(self):
        """Sólo cambia el estado, nunca crea ni modifica fotos o videos."""
        for trip in self:
            valid = trip.ruta_ids.filtered(
                lambda r: r.state == 'planificada' and r._has_carga_evidence()
            )
            if valid:
                valid.sudo().write({'state': 'cargada'})

    def action_reopen_packing(self):
        # El original deja todas las rutas 'planificada', con fotos intactas.
        # Restaurar sólo aquellas con evidencia posterior a una revisión de
        # composición; las fotos históricas nunca habilitan un nuevo despacho.
        with self.env.cr.savepoint():
            result = super().action_reopen_packing()
            self._tc_restore_valid_route_evidence()
        return result

    def action_ready_for_driver(self):
        """Auto-reparación segura de viajes ya reabiertos en versiones anteriores.

        Primero comprueba TODAS las rutas. Sólo después restaura sus estados y
        llama al flujo original; el savepoint revierte cualquier escritura
        si el controlador HTTP atrapa una excepción y devuelve un redirect.
        """
        self.env['transcash.hoja.ruta']._check_operator()
        with self.env.cr.savepoint():
            for trip in self.sorted('id'):
                if trip.company_id not in self.env.user.company_ids:
                    raise AccessError(_('No está autorizado para esta compañía.'))
                trip._lock_driver_operation(trip.chofer_usuario_id.id)
                self.env.cr.execute(
                    'SELECT id FROM transcash_embarque WHERE id=%s FOR UPDATE', (trip.id,)
                )
                trip.invalidate_recordset(['state', 'ruta_ids', 'objecion_pendiente', 'observacion_rechazo'])
                if trip.state != 'preparacion':
                    # Permitir que el método original comunique el error de estado.
                    continue
                if trip.objecion_pendiente or trip.observacion_rechazo:
                    raise UserError(_('Hay una objeción pendiente del chofer. Resuélvala antes de volver a enviar el viaje.'))
                if not trip.ruta_ids:
                    raise UserError(_('Agregue hojas de ruta antes de enviar el embarque.'))
                for route in trip.ruta_ids:
                    if route.state not in ('planificada', 'cargada'):
                        raise UserError(_(
                            'La ruta %(ruta)s está en estado %(estado)s. Revise su carga antes de enviarla.'
                        ) % {'ruta': route.name, 'estado': route.state})
                    if not route._has_carga_evidence():
                        if route.evidencia_carga_ids or route.video_carga:
                            raise UserError(_(
                                'La ruta %(ruta)s tiene fotos o videos, pero corresponden a una carga '
                                'anterior a su última modificación. Registre una evidencia NUEVA '
                                'de la carga actual para poder enviar el viaje.'
                            ) % {'ruta': route.name})
                        raise UserError(_(
                            'Falta una foto o video de carga en la ruta %(ruta)s. '
                            'Abra esa ruta y registre la evidencia antes de enviar el viaje.'
                        ) % {'ruta': route.name})
                trip._tc_restore_valid_route_evidence()
            return super().action_ready_for_driver()
