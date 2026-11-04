from odoo import api, fields, models


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
    is_documents_received = fields.Boolean(string='Documentación recibida (acción automática)')
    is_rejected = fields.Boolean(string='Etapa denegada')
    portal_sketch_enabled = fields.Boolean(string='Permitir subir croquis en el portal', help='En esta etapa el solicitante puede subir el croquis por primera vez desde su historial. Para corregir uno ya entregado, CONEDERA debe habilitar el permiso de croquis en la solicitud.')
    description = fields.Text(string='Descripción interna')

    _sql_constraints = [
        ('conedera_credit_stage_name_uniq', 'unique(name)', 'Ya existe una etapa con ese nombre.'),
    ]

    @api.model
    def _ensure_portal_sketch_stage(self):
        """Activar una sola vez la etapa de revisión existente (XML noupdate).

        Si el administrador después deshabilita el botón, una próxima actualización
        NO lo vuelve a activar automáticamente.
        """
        params = self.env['ir.config_parameter'].sudo()
        key = 'custom_web_credito_conedera.sketch_stage_configured'
        if params.get_param(key) == '1':
            return
        stages = self.sudo().with_context(active_test=False)
        if not stages.search_count([('portal_sketch_enabled', '=', True)]):
            review = self.env.ref('custom_web_credito_conedera.stage_credit_review', raise_if_not_found=False)
            if review:
                review.sudo().write({'portal_sketch_enabled': True})
        params.set_param(key, '1')
