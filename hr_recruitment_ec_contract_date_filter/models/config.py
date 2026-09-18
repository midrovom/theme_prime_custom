from odoo import models, fields, api
from datetime import datetime, timedelta

class HrEcOnboardingPackage(models.Model):
    _inherit = "hr.ec.onboarding.package"

    match_date = fields.Boolean(
        string="Coincide con filtro",
        compute="_compute_match_date",
        store=False,
    )

    @api.depends("generated_at")
    def _compute_match_date(self):
        """Marca True si el registro coincide con la fecha enviada en contexto"""
        selected_date = self.env.context.get("filter_date")
        for rec in self:
            if selected_date and rec.generated_at:
                try:
                    start = datetime.strptime(selected_date, "%Y-%m-%d")
                    end = start + timedelta(days=1)
                    rec.match_date = start <= rec.generated_at < end
                except Exception:
                    rec.match_date = True
            else:
                rec.match_date = True

