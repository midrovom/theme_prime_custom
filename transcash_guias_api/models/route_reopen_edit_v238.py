# -*- coding: utf-8 -*-
"""Edición controlada de rutas libres y retorno seguro de viajes sin aceptación.

La bitácora de carga permanece inmutable. Tras cambiar una ruta que tenía
fotografías/videos, debe documentarse nuevamente la carga en el próximo viaje.
"""
from odoo import fields, models, _
from odoo.exceptions import AccessError, UserError


class TranscashRouteReopenV238(models.Model):
    _inherit = 'transcash.hoja.ruta'

    tc_evidence_revision_after = fields.Datetime(
        string='Evidencias anteriores a última revisión', readonly=True, copy=False,
        help='Las evidencias previas son históricas y no autorizan nuevos despachos.')

    def _tc_check_reopen_for_edit(self):
        self._check_operator()
        for route in self:
            if route.company_id not in self.env.user.company_ids:
                raise AccessError(_('Esta hoja de ruta pertenece a otra compañía.'))
            if route.embarque_id or self.env['transcash.guia'].sudo().search_count([
                    ('hoja_ruta_id', '=', route.id), ('embarque_id', '!=', False)]):
                raise UserError(_('La ruta %s pertenece a un viaje; no puede modificarse.') % route.name)
            if route.state not in ('borrador', 'planificada', 'cargada'):
                raise UserError(_('La ruta %s tiene aceptación o movimiento registrado.') % route.name)
            if route.fecha_cierre_operativo or any(
                    g.state != 'registrada' or g.embarque_id or g.fecha_salida or
                    g.fecha_cierre_chofer or g.fecha_cierre_logistica
                    for g in route.guia_ids):
                raise UserError(_('La ruta %s contiene guías ya despachadas o entregadas.') % route.name)

    def _has_carga_evidence(self):
        self.ensure_one()
        if not self.tc_evidence_revision_after:
            return super()._has_carga_evidence()
        # La evidencia permanece accesible en el expediente, pero una nueva
        # composición de carga debe quedar documentada después de la revisión.
        return bool(self.evidencia_carga_ids.filtered(
            lambda ev: ev.fecha and ev.fecha > self.tc_evidence_revision_after))

    def action_tc_reopen_route_for_edit(self):
        self.ensure_one()
        self._tc_check_reopen_for_edit()
        # Bloqueo real de la hoja y de sus guías: otro operador puede tratar de
        # asignarlas a un embarque al mismo tiempo.
        self.env.cr.execute('SELECT id FROM transcash_hoja_ruta WHERE id=%s FOR UPDATE', (self.id,))
        self.invalidate_recordset(['state', 'embarque_id', 'guia_ids', 'seleccion_guia_ids'])
        guides = self.guia_ids
        if guides:
            self.env.cr.execute('SELECT id FROM transcash_guia WHERE id = ANY(%s) ORDER BY id FOR UPDATE', (guides.ids,))
            guides.invalidate_recordset(['state', 'embarque_id', 'hoja_ruta_id', 'fecha_salida',
                                         'fecha_cierre_chofer', 'fecha_cierre_logistica'])
        self._tc_check_reopen_for_edit()
        if self.state != 'borrador':
            revision = fields.Datetime.now() if self.evidencia_carga_ids or self.video_carga else self.tc_evidence_revision_after
            # Mantener las guías marcadas en el selector sin dejarlas asignadas:
            # al confirmar se vuelven a validar los filtros y el máximo de 100.
            selected_ids = sorted(set(self.seleccion_guia_ids.ids + guides.ids))
            if guides:
                guides.sudo().write({'hoja_ruta_id': False})
            self.sudo().write({
                'state': 'borrador',
                'seleccion_guia_ids': [(6, 0, selected_ids)],
                'reasignacion_autorizada': False,
                'reasignacion_autorizada_por_id': False,
                'tc_evidence_revision_after': revision,
            })
        return {'type': 'ir.actions.act_url',
                'url': '/transcash/operacion/rutas/%d/editar' % self.id,
                'target': 'self'}

    def action_tc_open_route_editor(self):
        self.ensure_one()
        self._tc_check_reopen_for_edit()
        if self.state != 'borrador':
            raise UserError(_('Primero pulse «Reabrir para modificar» esta hoja de ruta.'))
        return {'type': 'ir.actions.act_url',
                'url': '/transcash/operacion/rutas/%d/editar' % self.id,
                'target': 'self'}


class TranscashTripReopenV238(models.Model):
    _inherit = 'transcash.embarque'

    def action_reopen_packing(self):
        self.env['transcash.hoja.ruta']._check_operator()
        for trip in self:
            if trip.company_id not in self.env.user.company_ids:
                raise AccessError(_('El viaje pertenece a una compañía no autorizada.'))
            trip._lock_driver_operation(trip.chofer_usuario_id.id)
            self.env.cr.execute('SELECT id FROM transcash_embarque WHERE id=%s FOR UPDATE', (trip.id,))
            trip.invalidate_recordset(['state', 'aceptado_chofer', 'fecha_aceptacion_chofer',
                                       'fecha_salida', 'fecha_entrega', 'fecha_cierre_logistica',
                                       'estado_aprobacion', 'liquidacion_linea_id', 'ruta_ids', 'guia_ids'])
            if trip.state != 'embarcado' or not trip.ruta_ids or trip.aceptado_chofer or trip.fecha_aceptacion_chofer:
                raise UserError(_('Solo puede devolverse un viaje enviado al chofer que aún no haya aceptado.'))
            if trip.fecha_salida or trip.fecha_entrega or trip.fecha_cierre_logistica:
                raise UserError(_('El viaje ya registra salida o entrega y no puede volver a preparación.'))
            # La inspección de documentos contables no concede acceso al operador.
            # Solo esta relación se lee bajo sudo; los controles de usuario y
            # compañía, estado y aceptación siguen con el usuario original.
            if (trip.estado_aprobacion not in ('pendiente', 'no_aplica') or
                    trip.sudo().liquidacion_linea_id or trip.aprobado_fecha):
                raise UserError(_('El viaje tiene gestiones financieras; no puede volver a preparación.'))
            if self.env['transcash.pago.liquidacion.linea'].sudo().search_count([('embarque_id', '=', trip.id)]):
                raise UserError(_('El viaje ya está relacionado con una liquidación.'))
            if any(g.fecha_salida or g.fecha_cierre_chofer or g.fecha_cierre_logistica or
                   g.state not in ('registrada', 'embarque', 'embarcada') for g in trip.guia_ids):
                raise UserError(_('Hay guías que ya comenzaron el traslado o la entrega.'))
        # El método original preserva la objeción y su bitácora para exigir
        # resolución antes de liberar nuevamente al chofer.
        return super().action_reopen_packing()
