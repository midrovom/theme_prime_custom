# -*- coding: utf-8 -*-
"""Retirar UNA hoja de ruta de un viaje antes de aceptación del chofer.

La operación no elimina ruta, guías ni evidencia. Solo ajusta las relaciones
operativas cuando el embarque todavía puede cambiar su composición.
"""
from odoo import fields, models, _
from odoo.exceptions import AccessError, UserError


class EmbarqueRetirarRuta(models.Model):
    _inherit = 'transcash.embarque'

    def _tc_check_route_detachable(self, route):
        self.ensure_one()
        self.env['transcash.hoja.ruta']._check_operator()
        if self.company_id not in self.env.user.company_ids:
            raise AccessError(_('No está autorizado a modificar viajes de esta compañía.'))
        if not route or route.company_id != self.company_id or route.embarque_id != self:
            raise UserError(_('Esta hoja de ruta no pertenece al viaje seleccionado.'))
        if (self.state not in ('preparacion', 'embarcado') or
                self.aceptado_chofer or self.fecha_aceptacion_chofer or
                self.fecha_salida or self.fecha_entrega or self.fecha_cierre_logistica):
            raise UserError(_('El viaje ya fue aceptado, despachado o entregado. No se puede quitar la ruta.'))
        # La existencia de liquidaciones es una verificación INTERNA, no un
        # permiso de lectura que deba recibir el operario. Conservar el chequeo
        # de grupo/compañía arriba y elevar solo la lectura financiera.
        fiscal = self.sudo()
        if (self.estado_aprobacion not in ('pendiente', 'no_aplica') or
                fiscal.liquidacion_linea_id or self.legado_liquidacion_bloqueada or
                self.aprobado_fecha):
            raise UserError(_('El viaje ya tiene una gestión financiera que impide cambiar sus rutas.'))
        # El valor negociado es del VIAJE completo, no de una ruta. No dejarlo
        # vigente para una composición distinta sin nueva revisión del jefe.
        if fiscal.valor_acordado or fiscal.tarifa_referencial_total or fiscal.tarifa_id:
            raise UserError(_('El viaje tiene un valor de flete definido. El jefe de Logística debe revisarlo antes de retirar rutas.'))
        if (route.state == 'aceptada' or route.fecha_cierre_operativo or
                any(g.fecha_salida or g.fecha_cierre_chofer or g.fecha_cierre_logistica
                    or g.state not in ('registrada', 'embarque', 'embarcada')
                    for g in route.guia_ids)):
            raise UserError(_('La ruta ya tiene movimientos, aceptación o entregas registrados.'))
        route_guides = route.guia_ids
        if not route_guides or any(g.embarque_id != self for g in route_guides):
            raise UserError(_('Las guías de esta ruta no coinciden con el viaje. Revise su asignación.'))
        # No ocultar inconsistencias preexistentes al retirar solo una ruta.
        if set(self.ruta_ids.mapped('guia_ids').ids) != set(self.guia_ids.ids):
            raise UserError(_('Las hojas de ruta y las guías del viaje no coinciden. Revise antes de modificarlo.'))

    def action_tc_detach_route(self, route_id):
        """API ORM para PWA y asistente backend; bloqueos en el servidor."""
        self.ensure_one()
        self.env['transcash.hoja.ruta']._check_operator()
        try:
            route_id = int(route_id)
        except (ValueError, TypeError):
            raise UserError(_('Seleccione una hoja de ruta válida.'))
        if route_id <= 0:
            raise UserError(_('Seleccione una hoja de ruta válida.'))
        # Mantener el orden de locks del flujo de armado/aceptación.
        self._lock_driver_operation(self.chofer_usuario_id.id)
        self.env.cr.execute('SELECT id FROM transcash_embarque WHERE id=%s FOR UPDATE', (self.id,))
        self.invalidate_recordset(['state', 'aceptado_chofer', 'fecha_aceptacion_chofer',
                                   'ruta_ids', 'guia_ids', 'estado_aprobacion', 'liquidacion_linea_id'])
        route = self.env['transcash.hoja.ruta'].browse(route_id).exists()
        if not route:
            raise UserError(_('La hoja de ruta ya no existe.'))
        self.env.cr.execute('SELECT id FROM transcash_hoja_ruta WHERE id=%s FOR UPDATE', (route.id,))
        route.invalidate_recordset(['embarque_id', 'state', 'guia_ids', 'fecha_cierre_operativo'])
        guides = route.guia_ids
        if guides:
            self.env.cr.execute('SELECT id FROM transcash_guia WHERE id = ANY(%s) ORDER BY id FOR UPDATE', (sorted(guides.ids),))
            guides.invalidate_recordset(['embarque_id', 'hoja_ruta_id', 'state',
                                         'fecha_salida', 'fecha_cierre_chofer', 'fecha_cierre_logistica'])
        self.invalidate_recordset(['ruta_ids', 'guia_ids'])
        self._tc_check_route_detachable(route)
        # Un viaje enviado, todavía no aceptado, debe regresar al estado de
        # preparación antes de modificar su composición (flujo original).
        if self.state == 'embarcado':
            self.action_reopen_packing()
            self.invalidate_recordset(['state'])
            if self.state != 'preparacion':
                raise UserError(_('No fue posible devolver el viaje a preparación.'))
        # Las guías CONSERVAN su hoja de ruta; únicamente quedan fuera del viaje.
        guides.sudo().write({'embarque_id': False, 'state': 'registrada'})
        route.sudo().write({'embarque_id': False})
        self._message_log(body=_('Hoja de ruta %(route)s retirada del viaje por %(user)s. '
                                 'Se liberaron %(count)s guías para reutilización. '
                                 'La ruta y sus evidencias permanecen registradas.') % {
                                     'route': route.name, 'user': self.env.user.name,
                                     'count': len(guides),
                                 })
        return True

    def action_tc_open_detach_route_wizard(self):
        self.ensure_one()
        self.env['transcash.hoja.ruta']._check_operator()
        if self.company_id not in self.env.user.company_ids:
            raise AccessError(_('Compañía no autorizada.'))
        if self.state not in ('preparacion', 'embarcado') or self.aceptado_chofer or self.fecha_aceptacion_chofer:
            raise UserError(_('Solo se pueden retirar rutas antes de la aceptación del chofer.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Quitar ruta del viaje'),
            'res_model': 'tc.desvincular.ruta.wizard',
            'view_mode': 'form', 'target': 'new',
            'context': {'default_embarque_id': self.id},
        }


class DesvincularRutaWizard(models.TransientModel):
    _name = 'tc.desvincular.ruta.wizard'
    _description = 'Quitar una hoja de ruta de un embarque no aceptado'

    embarque_id = fields.Many2one('transcash.embarque', required=True, readonly=True)
    ruta_id = fields.Many2one('transcash.hoja.ruta', required=True,
                                                domain="[('embarque_id', '=', embarque_id)]")

    def action_confirm(self):
        self.ensure_one()
        self.embarque_id.action_tc_detach_route(self.ruta_id.id)
        return {'type': 'ir.actions.act_window', 'res_model': 'transcash.embarque',
                'res_id': self.embarque_id.id, 'view_mode': 'form', 'target': 'current'}
