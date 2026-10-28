# -*- coding: utf-8 -*-
"""Corrección segura de planificación previa a aceptación del chofer.

No toca rutas/viajes entregados ni el flujo financiero; las guías vuelven al
pool de planificación y la evidencia física se conserva en cada hoja de ruta.
"""
from odoo import models, _
from odoo.exceptions import AccessError, UserError


class HojaRutaEditable(models.Model):
    _inherit = 'transcash.hoja.ruta'

    def _tc_check_can_delete_route(self):
        self._check_operator()
        for route in self:
            if route.company_id not in self.env.user.company_ids:
                raise AccessError(_('La hoja de ruta pertenece a otra compañía.'))
            if route.embarque_id or self.env['transcash.guia'].sudo().search_count([
                    ('hoja_ruta_id', '=', route.id), ('embarque_id', '!=', False)]):
                raise UserError(_('La hoja %s ya se utilizó en un viaje. No se puede eliminar.') % route.name)
            if route.state not in ('borrador', 'planificada'):
                raise UserError(_('La hoja %s ya tiene carga o aceptación registrada; conserve su historial.') % route.name)
            if route.evidencia_carga_ids or route.video_carga or route.fecha_cierre_operativo:
                raise UserError(_('La hoja %s contiene evidencias o entregas; no se puede eliminar.') % route.name)
            if any(g.state != 'registrada' or g.fecha_cierre_chofer or g.fecha_salida for g in route.guia_ids):
                raise UserError(_('La hoja %s contiene guías que avanzaron en el proceso.') % route.name)

    def action_tc_delete_unassigned_route(self):
        self.ensure_one()
        self.unlink()
        return {'type': 'ir.actions.act_url', 'url': '/transcash/operacion/rutas?ok=eliminada', 'target': 'self'}

    def unlink(self):
        # La implementación original solo admite borradores; permitir también
        # planificadas sin embarque, sin borrar las guías importadas del ERP.
        self._check_operator()
        self.env.cr.execute('SELECT id FROM transcash_hoja_ruta WHERE id = ANY(%s) ORDER BY id FOR UPDATE', (self.ids,))
        self.invalidate_recordset(['state', 'embarque_id', 'guia_ids'])
        self._tc_check_can_delete_route()
        guides = self.mapped('guia_ids')
        if guides:
            self.env.cr.execute('SELECT id FROM transcash_guia WHERE id = ANY(%s) ORDER BY id FOR UPDATE', (guides.ids,))
            guides.invalidate_recordset(['hoja_ruta_id', 'embarque_id', 'state'])
            self._tc_check_can_delete_route()
            guides.sudo().write({'hoja_ruta_id': False})
        # Saltar únicamente el veto de borrador de la versión base v5.32;
        # las validaciones anteriores son más estrictas en evidencias y uso.
        return models.Model.unlink(self.sudo())


class EmbarqueEditable(models.Model):
    _inherit = 'transcash.embarque'

    def _tc_check_can_delete_trip(self):
        self.env['transcash.hoja.ruta']._check_operator()
        for trip in self:
            if trip.company_id not in self.env.user.company_ids:
                raise AccessError(_('El viaje pertenece a una compañía no autorizada.'))
            if (trip.state not in ('preparacion', 'embarcado') or trip.aceptado_chofer or
                    trip.fecha_aceptacion_chofer or trip.fecha_salida or trip.fecha_entrega or
                    trip.fecha_cierre_logistica):
                raise UserError(_('El viaje %s ya fue aceptado, despachado o cerrado; no se puede eliminar.') % trip.name)
            if (trip.estado_aprobacion not in ('pendiente', 'no_aplica') or
                    trip.liquidacion_linea_id or trip.legado_liquidacion_bloqueada or
                    trip.aprobado_fecha):
                raise UserError(_('El viaje %s tiene trámites económicos; no se puede eliminar.') % trip.name)
            if trip.objecion_ids or trip.objecion_pendiente or trip.observacion_rechazo:
                raise UserError(_('El viaje %s tiene objeciones registradas por el chofer; deben preservarse.') % trip.name)
            if set(trip.ruta_ids.mapped('guia_ids').ids) - set(trip.guia_ids.ids):
                raise UserError(_('Las rutas y guías del viaje %s están inconsistentes; revise antes de eliminar.') % trip.name)
            if any(r.state == 'aceptada' or r.fecha_cierre_operativo for r in trip.ruta_ids):
                raise UserError(_('El viaje %s tiene rutas aceptadas o entregadas.') % trip.name)
            if any(g.state not in ('registrada', 'embarque', 'embarcada') or
                   g.fecha_cierre_chofer or g.fecha_cierre_logistica or g.fecha_salida
                   for g in trip.guia_ids):
                raise UserError(_('El viaje %s tiene guías ya despachadas o entregadas.') % trip.name)
            if self.env['transcash.pago.liquidacion.linea'].sudo().search_count([('embarque_id', '=', trip.id)]):
                raise UserError(_('El viaje %s está asociado a una liquidación.') % trip.name)

    def action_tc_delete_unaccepted_trip(self):
        self.ensure_one()
        self.unlink()
        return {'type': 'ir.actions.act_url', 'url': '/transcash/embarques?ok=eliminado', 'target': 'self'}

    def unlink(self):
        if not self:
            return True
        self.env['transcash.hoja.ruta']._check_operator()
        for driver_id in sorted(set(self.mapped('chofer_usuario_id').ids)):
            self._lock_driver_operation(driver_id)
        self.env.cr.execute('SELECT id FROM transcash_embarque WHERE id = ANY(%s) ORDER BY id FOR UPDATE', (self.ids,))
        self.invalidate_recordset(['state', 'aceptado_chofer', 'fecha_aceptacion_chofer',
                                   'ruta_ids', 'guia_ids', 'liquidacion_linea_id'])
        self._tc_check_can_delete_trip()
        routes = self.mapped('ruta_ids')
        guides = self.mapped('guia_ids')
        if guides:
            self.env.cr.execute('SELECT id FROM transcash_guia WHERE id = ANY(%s) ORDER BY id FOR UPDATE', (guides.ids,))
            guides.invalidate_recordset(['state', 'embarque_id', 'fecha_salida'])
            self._tc_check_can_delete_trip()
        # Desvincular antes de eliminar: ambas FKs son ondelete=restrict.
        # No borrar guías ni evidencias y no cambiar su ruta original.
        if guides:
            guides.sudo().write({'embarque_id': False, 'state': 'registrada'})
        if routes:
            routes.sudo().write({'embarque_id': False})
        return models.Model.unlink(self.sudo())
