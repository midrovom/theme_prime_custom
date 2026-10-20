# -*- coding: utf-8 -*-
"""Auditoría de consultas analíticas. Solo administradores pueden leerla.

El controlador escribe con sudo tras comprobar identidad y permisos. Los usuarios
nunca leen este modelo directamente: exportan exclusivamente sus propios resultados
mediante una ruta con comprobación de usuario, empresa y CSRF.
"""
from datetime import timedelta
from odoo import api, fields, models


class TranscashAIRequest(models.Model):
    _name = 'transcash.inventory.ai.request'
    _description = 'Bitácora administrativa de consultas de IA Transcash'
    _order = 'create_date desc, id desc'

    user_id = fields.Many2one('res.users', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one('res.company', required=True, ondelete='cascade', index=True)
    snapshot_id = fields.Many2one('transcash.inventory.snapshot', ondelete='set null', index=True)
    question = fields.Text(string='Solicitud del usuario')
    state = fields.Selection([
        ('started', 'En proceso'),
        ('done', 'Realizada'),
        ('unavailable', 'No disponible'),
        ('failed', 'Error'),
    ], default='started', index=True, string='Estado')
    metrics = fields.Char(string='Indicadores solicitados')
    dimension = fields.Char(string='Agrupación')
    row_count = fields.Integer(string='Filas devueltas')
    duration_ms = fields.Integer(string='Duración (ms)')
    finished_at = fields.Datetime(string='Finalizada')
    sql_query = fields.Text(string='SQL ejecutado')
    sql_parameters = fields.Text(string='Parámetros de SQL')
    plan_json = fields.Text(string='Plan validado')
    # Se conserva el resultado exacto y limitado (máximo 50 filas) para poder
    # descargar Excel sin lanzar otra consulta ni confiar en valores del cliente.
    result_json = fields.Text(string='Resultado conservado para exportación')
    error_detail = fields.Text(string='Detalle del error')
    export_count = fields.Integer(string='Exportaciones')
    last_export_at = fields.Datetime(string='Última exportación')

    @api.model
    def cleanup_old_requests(self):
        """Retención de 30 días; el administrador puede reducirla por política."""
        cutoff = fields.Datetime.now() - timedelta(days=30)
        self.sudo().search([('create_date', '<', fields.Datetime.to_string(cutoff))]).unlink()
