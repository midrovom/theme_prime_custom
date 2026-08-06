from odoo import models, fields, api

class HrApplicant(models.Model):
    _inherit = 'hr.applicant'

    process_finalized = fields.Boolean(string="Proceso Finalizado", default=False)
    is_readonly_finalize = fields.Boolean(compute='_compute_is_readonly_finalize', store=False)

    @api.depends_context('uid')
    def _compute_is_readonly_finalize(self):
        for rec in self:
            rec.is_readonly_finalize = self.env.user.has_group(
                'custom_web_hr_datos_candidatos.group_applicant_readonly'
            )

    def action_finalize_process(self):
        self.ensure_one()
        self.process_finalized = True
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }
