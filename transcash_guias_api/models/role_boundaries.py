# -*- coding: utf-8 -*-
"""Separación de funciones sin cambiar el addon operativo Logística Transcash.

La ruta y la carga son responsabilidad del operador. El importe de un viaje
nuevo permanece en cero hasta que el jefe lo negocie; la aprobación conserva
la máquina de estados y los bloqueos originales de Logística v5.32.
"""
from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

FINANCE_GROUPS = (
    'logistica_transcash.group_logistica_manager,'
    'logistica_transcash.group_transcash_contabilidad'
)
MANAGER = 'logistica_transcash.group_logistica_manager'
OPERATOR = 'logistica_transcash.group_transcash_operador_rutas'


class TranscashEmbarqueRoles(models.Model):
    _inherit = 'transcash.embarque'

    # La ocultación en XML NO constituye seguridad. El atributo groups impide
    # además leer estos importes con RPC (search_read/read/web_read).
    tarifa_referencial_total = fields.Monetary(groups=FINANCE_GROUPS)
    tarifa_id = fields.Many2one(groups=FINANCE_GROUPS)
    notas_revision_logistica = fields.Text(groups=MANAGER)
    motivo_excepcion_pago = fields.Text(groups=MANAGER)


class TranscashTarifaRoles(models.Model):
    _inherit = 'transcash.tarifa.traslado'

    precio = fields.Monetary(groups=MANAGER)


class TranscashRutaRoles(models.Model):
    _inherit = 'transcash.hoja.ruta'

    tarifa_referencial = fields.Monetary(groups=FINANCE_GROUPS)
    tarifa_id = fields.Many2one(groups=FINANCE_GROUPS)


class TranscashArmarEmbarqueRoles(models.TransientModel):
    _inherit = 'transcash.armar.embarque.wizard'

    importe_total_estimado = fields.Monetary(groups=MANAGER)

    def action_confirm(self):
        """Operador crea embarque SIN negociar ni consultar importes.

        Jefe conserva comportamiento original del wizard. En particular, no
        alteramos embarques preexistentes ni el procedimiento de liquidación.
        """
        self.ensure_one()
        user = self.env.user
        if user.share or not (
            user.has_group(OPERATOR) or user.has_group(MANAGER)
        ):
            raise AccessError(_('Solo el personal interno de operaciones puede armar embarques.'))
        if user.has_group(MANAGER):
            return super().action_confirm()
        return self._tc_operator_confirm_unpriced()

    def _tc_operator_confirm_unpriced(self):
        """Reutiliza bloqueos y reglas funcionales del wizard original v5.32.

        No consulta tarifas ni almacena precio alguno, incluso para rutas de
        múltiples destinos. Un jefe podrá definir el valor antes de aprobar.
        """
        self.ensure_one()
        self.env['transcash.hoja.ruta']._check_operator()
        if not self.ruta_ids:
            raise UserError(_('Seleccione al menos una hoja de ruta.'))
        routes = self.ruta_ids.sorted('id')
        first = routes[0]
        if not self.proveedor_id or not self.chofer_usuario_id or not self.tipo_vehiculo or not self.placa:
            raise UserError(_('Seleccione transportista, chofer, vehículo y placa.'))
        if (first.company_id != self.company_id or
                first.proveedor_id != self.proveedor_id or
                first.chofer_usuario_id != self.chofer_usuario_id or
                first.tipo_vehiculo != self.tipo_vehiculo or
                (first.placa or '').strip().upper() != (self.placa or '').strip().upper()):
            raise UserError(_('La ruta seleccionada no corresponde a los datos del embarque.'))
        if first.company_id not in self.env.user.company_ids:
            raise AccessError(_('No está autorizado para esta compañía.'))

        trip_model = self.env['transcash.embarque']
        driver_id = first.chofer_usuario_id.id
        trip_model._lock_driver_operation(driver_id)
        existing = self.embarque_id
        if existing:
            if existing.company_id not in self.env.user.company_ids:
                raise AccessError(_('No está autorizado para este embarque.'))
            self.env.cr.execute(
                'SELECT id FROM transcash_embarque WHERE id=%s FOR UPDATE', (existing.id,)
            )
            existing.invalidate_recordset(['state'])
            if existing.state != 'preparacion' or existing.chofer_usuario_id != first.chofer_usuario_id:
                raise UserError(_('Solo se agregan rutas a un embarque en preparación del mismo chofer.'))
            if (existing.company_id != self.company_id or
                    existing.proveedor_id != self.proveedor_id or
                    existing.chofer_usuario_id != self.chofer_usuario_id or
                    existing.tipo_vehiculo != self.tipo_vehiculo or
                    (existing.placa or '').strip().upper() != (self.placa or '').strip().upper()):
                raise UserError(_('El embarque elegido pertenece a otro transporte o vehículo.'))
        elif trip_model._active_driver_trip(driver_id):
            raise UserError(_('Este chofer ya tiene un embarque activo. Agregue las rutas a ese viaje.'))

        for route in routes:
            if route.state not in ('planificada', 'cargada') or route.embarque_id:
                raise UserError(_('La ruta %s no está disponible.') % route.name)
            if (route.company_id != first.company_id or
                    route.chofer_usuario_id != first.chofer_usuario_id or
                    route.proveedor_id != first.proveedor_id or
                    route.tipo_vehiculo != first.tipo_vehiculo or
                    (route.placa or '').strip().upper() != (first.placa or '').strip().upper()):
                raise UserError(_('Las rutas deben compartir compañía, chofer, transportista, tipo y placa.'))
        guia_ids = routes.mapped('guia_ids')
        if not guia_ids or any(g.embarque_id for g in guia_ids):
            raise UserError(_('Alguna ruta no tiene guías disponibles.'))
        if len(existing.guia_ids) + len(guia_ids) > 100:
            raise UserError(_('Se excede el máximo de 100 guías por embarque.'))

        if not existing:
            # El operador NO selecciona destino de facturación ni tarifa.
            # Si hay un solo destino, sirve como referencia provisional.
            destinos = routes.mapped('destino_id')
            provisional = destinos if len(destinos) == 1 else False
            vals = {
                'company_id': first.company_id.id,
                'chofer_usuario_id': driver_id,
                'proveedor_id': first.proveedor_id.id,
                'placa': first.placa,
                'origen': first.origen,
                'tipo_vehiculo': first.tipo_vehiculo,
                'valor_acordado': 0.0,
                'tarifa_referencial_total': 0.0,
            }
            if provisional:
                vals['destino_tarifa_id'] = provisional.id
            existing = trip_model.sudo().create(vals)

        routes.sudo().write({'embarque_id': existing.id})
        guia_ids.sudo().write({'embarque_id': existing.id})
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'transcash.embarque',
            'res_id': existing.id,
            'view_mode': 'form',
            'target': 'current',
        }
