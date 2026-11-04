from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError


class ConederaCreditAccessWizard(models.TransientModel):
    _name = 'conedera.credit.access.wizard'
    _description = 'Habilitar permisos de actualización del portal de crédito'

    application_id = fields.Many2one(
        'conedera.credit.application', string='Solicitud de crédito',
        required=True, readonly=True)
    allow_history = fields.Boolean(string='Solicitud de crédito (actualizar formulario)')
    allow_documentation = fields.Boolean(string='Ingreso de documentos (actualizar archivos)')
    allow_sketch = fields.Boolean(string='Croquis del cliente (volver a completar ubicación y archivo)')
    document_access_allowed = fields.Boolean(
        related='application_id.document_access_allowed', readonly=True)
    sketch_stage_enabled = fields.Boolean(
        related='application_id.stage_id.portal_sketch_enabled', readonly=True)

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        application_id = self.env.context.get('default_application_id') or self.env.context.get('active_id')
        if application_id:
            application = self.env['conedera.credit.application'].browse(application_id).exists()
            if application:
                values['application_id'] = application.id
                enabled = application.portal_enabled_sections()
                values.update({
                    'allow_history': 'history' in enabled,
                    'allow_documentation': 'documentation' in enabled,
                    'allow_sketch': 'sketch' in enabled,
                })
        return values

    def action_apply(self):
        self.ensure_one()
        if not (
            (
                self.env.user.has_group('custom_web_credito_conedera.group_credit_portal_update_manager')
                and self.env.user.has_group('custom_web_credito_conedera.group_credit_manager')
            )
            or self.env.user.has_group('custom_web_credito_conedera.group_credit_administrator')
        ):
            raise AccessError(_('No tiene permisos para habilitar la actualización del portal.'))
        application = self.application_id.exists()
        if not application or not application.portal_user_id:
            raise UserError(_('La solicitud no tiene un usuario de portal asociado.'))
        selected = {
            name for field_name, name in (
                ('allow_history', 'history'),
                ('allow_documentation', 'documentation'),
                ('allow_sketch', 'sketch'),
            ) if self[field_name]
        }
        application.sudo().write({
            'portal_update_scope': application.portal_scope_from_sections(selected),
            'portal_update_allowed_at': fields.Datetime.now(),
            'portal_update_allowed_by': self.env.user.id,
        })
        return {'type': 'ir.actions.act_window_close'}
