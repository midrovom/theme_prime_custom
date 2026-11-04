from odoo import fields, models


class ConederaCreditStageHistory(models.Model):
    _name = 'conedera.credit.stage.history'
    _description = 'Historial de etapas de solicitud de crédito'
    _order = 'date desc, id desc'

    application_id = fields.Many2one(
        'conedera.credit.application', string='Solicitud', required=True,
        ondelete='cascade', index=True,
    )
    stage_id = fields.Many2one('conedera.credit.stage', string='Etapa', required=True, ondelete='restrict')
    date = fields.Datetime(string='Fecha y hora', required=True, default=fields.Datetime.now)
    user_id = fields.Many2one('res.users', string='Responsable', default=lambda self: self.env.user, ondelete='set null')
    notes = fields.Char(string='Observación')
    visible_to_portal = fields.Boolean(string='Visible para el solicitante', default=True)
