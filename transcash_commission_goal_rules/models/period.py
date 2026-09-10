from calendar import monthrange
from datetime import date, timedelta

from odoo import Command, _, api, fields, models
from odoo.exceptions import ValidationError


class CommissionPeriod(models.Model):
    _inherit = "commission.period"

    project_rule_ids = fields.One2many(
        "commission.project.rule",
        "period_id",
        string="Proyectos por origen",
        help=(
            "Reglas de comisión de vendedores de proyectos aplicables a este "
            "período. Una regla activa de proyecto también habilita al vendedor "
            "para aparecer en la liquidación, aunque no tenga meta retail."
        ),
    )
    manager_goal_rule_ids = fields.One2many(
        "commission.manager.goal.rule",
        "period_id",
        string="Gestión de administradores",
    )

    # Compatibilidad con versiones anteriores de esta extensión.
    manager_seller_rule_ids = fields.One2many(
        "commission.manager.seller.rule",
        "period_id",
        string="Detalles de gestión (compatibilidad)",
    )

    liquidation_commission_penalty_percent = fields.Float(
        string="Reducción de comisión por no cumplir liquidación (%)",
        digits=(16, 4),
        default=0.0,
        help=(
            "Si un vendedor no alcanza una meta de liquidación aplicable, se "
            "descuenta este porcentaje de su comisión de ventas (comisión propia "
            "+ proyectos). La comisión de gestión del administrador no se reduce."
        ),
    )
    liquidation_penalty_exempt_seller_ids = fields.Many2many(
        "commission.seller",
        "commission_period_liq_penalty_exempt_rel",
        "period_id",
        "seller_id",
        string="Vendedores exentos de restricción",
        domain=[("active", "=", True), ("role", "in", ["seller", "project", "hybrid"])],
        help=(
            "Estos vendedores no reciben reducción de comisión aunque no alcancen "
            "la meta de liquidación del período."
        ),
    )

    @api.constrains("liquidation_commission_penalty_percent")
    def _check_liquidation_commission_penalty_percent(self):
        for rec in self:
            if not 0.0 <= rec.liquidation_commission_penalty_percent <= 100.0:
                raise ValidationError(
                    _("La reducción por incumplir la meta de liquidación debe estar entre 0% y 100%.")
                )

    def _next_available_copy_dates(self):
        """Devuelve el siguiente rango libre, respetando meses calendario.

        Si el origen es un mes completo (01 al último día), la copia también
        será un mes completo. Para otros rangos conserva la duración original.
        """
        self.ensure_one()
        duration = self.date_end - self.date_start
        source_is_calendar_month = (
            self.date_start.year == self.date_end.year
            and self.date_start.month == self.date_end.month
            and self.date_start.day == 1
            and self.date_end.day
            == monthrange(self.date_end.year, self.date_end.month)[1]
        )

        def next_calendar_month(after_date):
            year = after_date.year + (1 if after_date.month == 12 else 0)
            month = 1 if after_date.month == 12 else after_date.month + 1
            start = date(year, month, 1)
            end = date(year, month, monthrange(year, month)[1])
            return start, end

        if source_is_calendar_month:
            candidate_start, candidate_end = next_calendar_month(self.date_start)
        else:
            candidate_start = self.date_end + timedelta(days=1)
            candidate_end = candidate_start + duration

        while True:
            overlap = self.search([
                ("id", "!=", self.id),
                ("state", "!=", "cancelled"),
                ("date_start", "<=", candidate_end),
                ("date_end", ">=", candidate_start),
            ], order="date_end desc", limit=1)
            if not overlap:
                return candidate_start, candidate_end
            if source_is_calendar_month:
                candidate_start, candidate_end = next_calendar_month(candidate_start)
            else:
                candidate_start = overlap.date_end + timedelta(days=1)
                candidate_end = candidate_start + duration

    def action_duplicate_period(self):
        self.ensure_one()
        new_period = self.copy()
        return {
            "type": "ir.actions.act_window",
            "res_model": "commission.period",
            "res_id": new_period.id,
            "view_mode": "form",
            "target": "current",
        }

    def copy(self, default=None):
        """Duplica la configuración mensual completa, nunca la liquidación.

        Se copian como una sola plantilla mensual:
        - metas de vendedores y sus rangos;
        - reglas de proyectos/origen del período;
        - metas de locales;
        - gestión de administradores y detalle de vendedores;
        - reglas de bono de liquidación.

        No se copian resultados ni liquidaciones calculadas.
        """
        self.ensure_one()
        default = dict(default or {})

        if "date_start" not in default or "date_end" not in default:
            next_start, next_end = self._next_available_copy_dates()
            default.setdefault("date_start", next_start)
            default.setdefault("date_end", next_end)

        default.setdefault("name", _("%s (copia)") % self.name)
        default.setdefault(
            "liquidation_commission_penalty_percent",
            self.liquidation_commission_penalty_percent,
        )
        default.setdefault(
            "liquidation_penalty_exempt_seller_ids",
            [Command.set(self.liquidation_penalty_exempt_seller_ids.ids)],
        )
        default.update({
            "state": "draft",
            "settlement_id": False,
            # Se copian manualmente para controlar duplicidades y referencias.
            "target_ids": [],
            "project_rule_ids": [],
            "location_target_ids": [],
            "manager_rule_ids": [],  # regla legacy del módulo base
            "manager_goal_rule_ids": [],
            "liquidation_rule_ids": [],
        })

        new_period = super().copy(default)

        for target in self.target_ids:
            target.copy_to_period(new_period)
        for project_rule in self.project_rule_ids:
            project_rule.copy_to_period(new_period)
        for location_target in self.location_target_ids:
            location_target.copy_to_period(new_period)
        for management in self.manager_goal_rule_ids:
            management.copy_to_period(new_period)
        for liquidation_rule in self.liquidation_rule_ids:
            liquidation_rule.copy_to_period(new_period)

        return new_period
