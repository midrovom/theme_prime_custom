import logging
from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class HrApplicant(models.Model):
    _inherit = "hr.applicant"

    process_finalized = fields.Boolean(string="Proceso Finalizado", default=False,)
    is_readonly_finalize = fields.Boolean(string="Usuario readonly después de finalizar", compute="_compute_is_readonly_finalize",
        store=False,
    )

    @api.depends_context("uid")
    def _compute_is_readonly_finalize(self):
        has_group = self.env.user.has_group(
            "custom_web_hr_datos_candidatos.group_applicant_readonly"
        )

        for rec in self:
            rec.is_readonly_finalize = has_group

    def action_finalize_process(self):
        self.ensure_one()

        self.write({
            "process_finalized": True,
        })

        return {
            "type": "ir.actions.client",
            "tag": "reload",
        }

