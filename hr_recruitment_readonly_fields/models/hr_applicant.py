import logging
_logger = logging.getLogger(__name__)

from odoo import models, fields, api

class HrApplicant(models.Model):
    _inherit = 'hr.applicant'

    process_finalized = fields.Boolean(string="Proceso Finalizado", default=False)
    is_readonly_finalize = fields.Boolean(compute='_compute_is_readonly_finalize', store=False)

    @api.depends_context('uid')
    def _compute_is_readonly_finalize(self):
        for rec in self:
            valor = self.env.user.has_group(
                'custom_web_hr_datos_candidatos.group_applicant_readonly'
            )
            rec.is_readonly_finalize = valor
            _logger.info(">>> Compute is_readonly_finalize para %s: %s",
                         self.env.user.login, valor)

    def action_finalize_process(self):
        self.ensure_one()
        self.process_finalized = True
        _logger.info(">>> action_finalize_process ejecutado en applicant %s, "
                     "process_finalized=%s, is_readonly_finalize=%s",
                     self.id, self.process_finalized, self.is_readonly_finalize)
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }
