from odoo import api, fields, models

class HrApplicant(models.Model):
    _inherit = "hr.applicant"

    portal_user_id = fields.Many2one(
        "res.users", string="Usuario Portal", index=True,
        ondelete="set null", copy=False
    )
    phase_1_completed = fields.Boolean(string="Fase 1 completada", default=False, copy=False)
    phase_2_completed = fields.Boolean(string="Fase 2 completada", default=False, copy=False)
    phase_3_completed = fields.Boolean(string="Fase 3 completada", default=False, copy=False)
    form2_portal_enabled = fields.Boolean(
        string="Formulario 2 habilitado en portal",
        default=False,
        copy=False,
        help="Se activa automáticamente cuando la postulación entra en la etapa con secuencia 3 (Ficha Tecnica).",
    )

    @api.model_create_multi
    def create(self, vals_list):
        if self.env.user.has_group("base.group_portal"):
            for vals in vals_list:
                vals.setdefault("portal_user_id", self.env.user.id)
        records = super().create(vals_list)
        records._enable_form2_when_stage_3()
        return records

    def write(self, vals):
        result = super().write(vals)
        if "stage_id" in vals:
            self._enable_form2_when_stage_3()
        return result

    def _enable_form2_when_stage_3(self):
        """Habilita el Formulario 2 cuando la postulación entra en secuencia 3."""
        for record in self:
            if record.stage_id and record.stage_id.sequence == 3 and not record.form2_portal_enabled:
                record.with_context(skip_form2_stage_trigger=True).write({
                    "form2_portal_enabled": True,
                })

    def _portal_can_continue_form2(self, user=None):
        user = user or self.env.user
        return bool(
            self._portal_can_access(user)
            and self.form2_portal_enabled
        )

    def _portal_can_access(self, user=None):
        user = user or self.env.user
        return bool(user and user.has_group("base.group_portal") and
                    all(rec.portal_user_id.id == user.id for rec in self))

    def _complete_phase_2(self):
        self.ensure_one()
        if not self._portal_can_access():
            return False
        self.write({"phase_2_completed": True})
        return True
