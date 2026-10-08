from odoo import _, api, fields, models
from odoo.exceptions import UserError


class HrApplicant(models.Model):
    _inherit = 'hr.applicant'

    portal_update_scope = fields.Selection(
        [
            ('none', 'Ninguna sección'),
            ('history', 'Historial de postulación'),
            ('documentation', 'Ingreso de documentación'),
            ('both', 'Historial + documentación'),
        ],
        string='Sección habilitada para actualización',
        copy=False,
        default='none',
        help='Define qué puede modificar el postulante desde el portal cuando RRHH aplique el permiso.',
    )
    portal_update_allowed = fields.Boolean(
        string='Actualización desde portal habilitada',
        compute='_compute_portal_update_allowed',
        store=True,
        copy=False,
        help='Indica si existe al menos una sección habilitada para actualización.',
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
    required_document_total = fields.Integer(
        string='Total documentos obligatorios',
        compute='_compute_documentation_metrics',
    )
    required_document_uploaded = fields.Integer(
        string='Documentos obligatorios cargados',
        compute='_compute_documentation_metrics',
    )
    required_document_missing = fields.Integer(
        string='Documentos obligatorios faltantes',
        compute='_compute_documentation_metrics',
    )
    documentation_recommendation_count = fields.Integer(
        string='Cantidad de recomendaciones',
        compute='_compute_documentation_metrics',
    )
    documentation_is_complete = fields.Boolean(
        string='Expediente completo',
        compute='_compute_documentation_metrics',
    )

    @api.depends('portal_update_scope')
    def _compute_portal_update_allowed(self):
        for applicant in self:
            applicant.portal_update_allowed = applicant.portal_update_scope not in (False, 'none')

    def portal_can_update_history(self):
        self.ensure_one()
        return self.portal_update_scope in ('history', 'both')

    def portal_can_update_documentation(self):
        self.ensure_one()
        return self.portal_update_scope in ('documentation', 'both')

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

    @api.depends(
        'applicant_documentation_ids',
        'applicant_documentation_ids.required_document_total',
        'applicant_documentation_ids.required_document_uploaded',
        'applicant_documentation_ids.required_document_missing',
        'applicant_documentation_ids.recommendation_count',
        'applicant_documentation_ids.is_complete',
    )
    def _compute_documentation_metrics(self):
        for applicant in self:
            documentation = applicant.applicant_documentation_ids[:1]
            if documentation:
                applicant.required_document_total = documentation.required_document_total
                applicant.required_document_uploaded = documentation.required_document_uploaded
                applicant.required_document_missing = documentation.required_document_missing
                applicant.documentation_recommendation_count = documentation.recommendation_count
                applicant.documentation_is_complete = documentation.is_complete
            else:
                applicant.required_document_total = 0
                applicant.required_document_uploaded = 0
                applicant.required_document_missing = 0
                applicant.documentation_recommendation_count = 0
                applicant.documentation_is_complete = False

    def action_open_portal_update_wizard(self):
        self.ensure_one()
        if not self.env.user.has_group('custom_web_hr_historial_postulaciones.group_portal_update_manager'):
            raise UserError(_('No tiene permisos para habilitar actualizaciones desde el portal.'))
        if not self.portal_user_id:
            raise UserError(_('Esta postulación no tiene un usuario de portal asociado.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Habilitar permiso del portal'),
            'res_model': 'portal.update.permission.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_applicant_id': self.id,
                'default_portal_update_scope': self.portal_update_scope or 'none',
            },
        }

    def action_apply_portal_update(self):
        self.ensure_one()
        if not self.portal_user_id:
            raise UserError(_('Esta postulación no tiene un usuario de portal asociado.'))
        self.write({
            'portal_update_allowed_at': fields.Datetime.now(),
            'portal_update_allowed_by': self.env.user.id,
        })
        return True

    def write(self, vals):
        # Evita que un cambio de etapa haga desaparecer la documentación ya registrada.
        return super().write(vals)
