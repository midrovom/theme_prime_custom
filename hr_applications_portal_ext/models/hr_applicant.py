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

    @api.model_create_multi
    def create(self, vals_list):
        if self.env.user.has_group("base.group_portal"):
            for vals in vals_list:
                vals.setdefault("portal_user_id", self.env.user.id)
        return super().create(vals_list)

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
