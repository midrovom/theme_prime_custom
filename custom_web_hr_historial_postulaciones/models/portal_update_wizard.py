from odoo import _, api, fields, models
from odoo.exceptions import UserError


class PortalUpdatePermissionWizard(models.TransientModel):
    _name = 'portal.update.permission.wizard'
    _description = 'Permisos de actualización del portal'

    applicant_id = fields.Many2one(
        'hr.applicant',
        string='Postulación',
        required=True,
        readonly=True,
    )
    portal_update_scope = fields.Selection(
        [
            ('none', 'Ninguna sección'),
            ('history', 'Historial de postulación'),
            ('documentation', 'Ingreso de documentación'),
            ('both', 'Historial + documentación'),
        ],
        string='¿Qué puede actualizar el postulante?',
        required=True,
        default='none',
    )

    @api.model
    def default_get(self, fields_list):
        vals = super().default_get(fields_list)
        applicant_id = self.env.context.get('active_id')
        if applicant_id:
            applicant = self.env['hr.applicant'].browse(applicant_id).exists()
            if applicant:
                vals['applicant_id'] = applicant.id
                vals['portal_update_scope'] = applicant.portal_update_scope or 'none'
        return vals

    def action_apply(self):
        self.ensure_one()
        if not self.env.user.has_group('custom_web_hr_historial_postulaciones.group_portal_update_manager'):
            raise UserError(_('No tiene permisos para gestionar los permisos de actualización del portal.'))
        applicant = self.applicant_id
        if not applicant or not applicant.portal_user_id:
            raise UserError(_('Esta postulación no tiene un usuario de portal asociado.'))

        applicant.write({
            'portal_update_scope': self.portal_update_scope,
            'portal_update_allowed_at': fields.Datetime.now(),
            'portal_update_allowed_by': self.env.user.id,
        })
        return {'type': 'ir.actions.act_window_close'}
