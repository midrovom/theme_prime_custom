from odoo import _, api, fields, models
from odoo.exceptions import UserError


class HrApplicant(models.Model):
    _inherit = 'hr.applicant'

    portal_update_allowed = fields.Boolean(
        string='Permitir actualización desde portal',
        copy=False,
        default=False,
        help='Cuando está activo, el postulante puede editar nuevamente la información enviada desde el portal.',
    )
    portal_update_allowed_at = fields.Datetime(
        string='Actualización habilitada el',
        copy=False,
        readonly=True,
    )
    portal_update_allowed_by = fields.Many2one(
        'res.users',
        string='Actualización habilitada por',
        copy=False,
        readonly=True,
    )
    applicant_documentation_ids = fields.One2many(
        'applicant.documentation',
        'applicant_id',
        string='Documentación de ingreso',
    )

    documentation_required = fields.Boolean(
        string='Documentación habilitada',
        compute='_compute_documentation_required',
    )
    documentation_complete = fields.Boolean(
        string='Documentación completa',
        compute='_compute_documentation_complete',
    )

    @api.depends('stage_id.sequence')
    def _compute_documentation_required(self):
        for applicant in self:
            applicant.documentation_required = bool(
                applicant.stage_id and applicant.stage_id.sequence >= 3
            )

    @api.depends('applicant_documentation_ids', 'applicant_documentation_ids.is_complete')
    def _compute_documentation_complete(self):
        for applicant in self:
            applicant.documentation_complete = any(
                documentation.is_complete
                for documentation in applicant.applicant_documentation_ids
            )

    def action_allow_portal_update(self):
        self.ensure_one()
        if not self.portal_user_id:
            raise UserError(_('Esta postulación no tiene un usuario de portal asociado.'))
        self.write({
            'portal_update_allowed': True,
            'portal_update_allowed_at': fields.Datetime.now(),
            'portal_update_allowed_by': self.env.user.id,
        })
        return True

    def action_revoke_portal_update(self):
        self.write({'portal_update_allowed': False})
        return True

    def write(self, vals):
        # Evita que un cambio de etapa haga desaparecer la documentación ya registrada.
        return super().write(vals)
