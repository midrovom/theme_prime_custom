from datetime import timedelta

from odoo import _, api, fields, models


class CommissionPeriod(models.Model):
    _inherit = "commission.period"

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

    def _next_available_copy_dates(self):
        """Devuelve un rango consecutivo sin solaparse con otros períodos.

        Odoo guarda el duplicado inmediatamente. Por eso no podemos copiar las
        mismas fechas: la restricción del módulo base impediría crear el nuevo
        período. Conservamos la duración y buscamos el primer rango libre.
        """
        self.ensure_one()
        duration = self.date_end - self.date_start
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
        """Duplica el período junto con toda la parametrización de metas.

        Se copian:
        - metas de vendedores y sus rangos;
        - metas de locales;
        - gestión de administradores y sus vendedores a cargo.

        Las liquidaciones no se copian. El nuevo período siempre queda en
        borrador y con un rango de fechas consecutivo disponible.
        """
        self.ensure_one()
        default = dict(default or {})

        if "date_start" not in default or "date_end" not in default:
            next_start, next_end = self._next_available_copy_dates()
            default.setdefault("date_start", next_start)
            default.setdefault("date_end", next_end)

        default.setdefault("name", _("%s (copia)") % self.name)
        default.update({
            "state": "draft",
            "settlement_id": False,
            # Evita que copy_data replique automáticamente relaciones antes de
            # que podamos controlar duplicados y orden de creación.
            "target_ids": [],
            "location_target_ids": [],
            "manager_rule_ids": [],
            "manager_goal_rule_ids": [],
        })

        new_period = super().copy(default)

        for target in self.target_ids:
            target.copy_to_period(new_period)
        for location_target in self.location_target_ids:
            location_target.copy_to_period(new_period)
        for management in self.manager_goal_rule_ids:
            management.copy_to_period(new_period)

        return new_period
