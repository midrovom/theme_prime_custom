from odoo import fields, models


class ConederaCreditStage(models.Model):
    _name = 'conedera.credit.stage'
    _description = 'Etapa de solicitud de crédito CONEDERA'
    _order = 'sequence, id'

    name = fields.Char(string='Etapa', required=True, translate=True)
    sequence = fields.Integer(default=10, index=True)
    active = fields.Boolean(default=True)
    fold = fields.Boolean(string='Plegada en el kanban')
    is_initial = fields.Boolean(string='Etapa inicial')
    is_approved = fields.Boolean(string='Etapa de aprobación')
    is_rejected = fields.Boolean(string='Etapa denegada')
    description = fields.Text(string='Descripción interna')

    _sql_constraints = [
        ('conedera_credit_stage_name_uniq', 'unique(name)', 'Ya existe una etapa con ese nombre.'),
    ]
