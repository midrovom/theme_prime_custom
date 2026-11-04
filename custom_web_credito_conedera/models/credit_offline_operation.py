"""Confirmaciones de envíos diferidos; evita repetir una corrección o documentos.

Nunca almacena datos del formulario ni binarios: solo identificadores de la operación.
"""
from odoo import fields, models


class CreditOfflineOperation(models.Model):
    _name = 'conedera.credit.offline.operation'
    _description = 'Confirmación de envío offline de solicitud de crédito'
    _order = 'create_date desc'

    token = fields.Char(required=True, index=True, readonly=True)
    user_id = fields.Many2one('res.users', required=True, readonly=True)
    company_id = fields.Many2one('res.company', required=True, readonly=True)
    website_id = fields.Many2one('website', required=True, readonly=True)
    application_id = fields.Many2one('conedera.credit.application', readonly=True, ondelete='cascade')
    operation = fields.Selection([
        ('create', 'Nueva solicitud'), ('update', 'Actualizar solicitud'),
        ('documents', 'Documentos solicitados')], required=True, readonly=True)

    _sql_constraints = [
        ('unique_offline_token', 'unique(token)', 'El envío offline ya fue registrado.'),
    ]
