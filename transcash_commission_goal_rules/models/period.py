from odoo import fields, models


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
