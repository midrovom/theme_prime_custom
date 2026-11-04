from odoo import api, fields, models


class ResUsers(models.Model):
    _inherit = 'res.users'
    credit_portal_permission_manager_enabled = fields.Boolean(
        string='Permiso adicional: habilitar correcciones del portal',
        compute='_compute_credit_portal_permission_manager_enabled',
        inverse='_inverse_credit_portal_permission_manager_enabled',
        help='Permiso adicional para el revisor. Los administradores de crédito ya disponen de acceso completo.'
    )


    @api.depends('groups_id')
    def _compute_credit_portal_permission_manager_enabled(self):
        group = self.env.ref('custom_web_credito_conedera.group_credit_portal_update_manager', raise_if_not_found=False)
        for user in self:
            user.credit_portal_permission_manager_enabled = bool(group and group in user.groups_id)

    def _inverse_credit_portal_permission_manager_enabled(self):
        group = self.env.ref('custom_web_credito_conedera.group_credit_portal_update_manager', raise_if_not_found=False)
        if group:
            for user in self:
                # No permitir asignar privilegios internos a un usuario del portal.
                if user.credit_portal_permission_manager_enabled and user.share:
                    from odoo.exceptions import UserError
                    from odoo import _
                    raise UserError(_('Este permiso de administración solo es para usuarios internos.'))
                user.write({'groups_id': [(4 if user.credit_portal_permission_manager_enabled else 3, group.id)]})
