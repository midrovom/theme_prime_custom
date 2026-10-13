"""Idempotency receipts for media submitted after an offline period.

Records are deliberately server-side and cannot be modified by a portal user.
"""
from odoo import fields, models


class TranscashSyncOperacion(models.Model):
    _name = 'transcash.sync.operacion'
    _description = 'Confirmación de sincronización móvil'
    _order = 'create_date desc'

    client_uuid = fields.Char(required=True, index=True, readonly=True, copy=False)
    guia_id = fields.Many2one('transcash.guia', required=True, readonly=True, ondelete='cascade')
    usuario_id = fields.Many2one('res.users', required=True, readonly=True, ondelete='restrict')
    tipo = fields.Selection([('evidencia', 'Evidencia'), ('rotura', 'Rotura')], required=True, readonly=True)
    registro_id = fields.Integer('ID del registro generado', readonly=True)
    fecha_captura_dispositivo = fields.Char('Fecha declarada por el móvil', readonly=True)

    _sql_constraints = [
        ('transcash_client_uuid_unique', 'unique(client_uuid)', 'La operación móvil ya fue recibida.'),
    ]
