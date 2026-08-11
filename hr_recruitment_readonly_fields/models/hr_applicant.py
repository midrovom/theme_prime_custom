import logging
from odoo import api, fields, models
from odoo.exceptions import AccessError

class HrApplicant(models.Model):
    _inherit = "hr.applicant"

    process_finalized = fields.Boolean(string="Proceso Finalizado", default=False,)
    is_readonly_finalize = fields.Boolean(string="Usuario con readonly", compute="_compute_is_readonly_finalize",
        store=False,
    )

    @api.depends_context("uid")
    def _compute_is_readonly_finalize(self):
        has_group = self.env.user.has_group(
            "custom_web_hr_datos_candidatos.group_applicant_readonly"
        )

        for record in self:
            record.is_readonly_finalize = has_group

    def action_finalize_process(self):
        self.ensure_one()
        self.write({
            "process_finalized": True,
        })

        return {
            "type": "ir.actions.client",
            "tag": "reload",
        }

    def action_reopen_process(self):
        self.ensure_one()

        if not self.env.user.has.group(
            "hr_recruitment.group_hr_recruitment_manager"
        ):
            raise AccessError("Solo el Administrador puede reabirir el proceso.")

        self.process_finalized = False

        return {
            "type": "ir.actions.client",
            "tag": "reload",
        }



