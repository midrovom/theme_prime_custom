"""Compatibilidad: asistentes antiguos de la V5.5 deshabilitados.
Se conservan los nombres técnicos para que actualizaciones NO dejen vistas huérfanas.
Sin conexión con modelos del módulo account.
"""
from odoo import fields, models, _
from odoo.exceptions import UserError


class LegacyGuideLiquidacionWizard(models.TransientModel):
    _name = 'transcash.liquidacion.wizard'
    _description = 'Asistente histórico de liquidación deshabilitado'

    guia_id = fields.Many2one('transcash.guia', readonly=True)

    def action_confirm(self):
        raise UserError(_('La liquidación de guías antiguas está deshabilitada. Use Liquidaciones y pagos por embarque.'))


class LegacyEmbarqueLiquidacionWizard(models.TransientModel):
    _name = 'transcash.embarque.liquidacion.wizard'
    _description = 'Asistente contable histórico deshabilitado'

    embarque_id = fields.Many2one('transcash.embarque', readonly=True)

    def action_confirm(self):
        raise UserError(_('Los fletes ahora los negocia Logística. Use el botón Negociar valor del viaje.'))
