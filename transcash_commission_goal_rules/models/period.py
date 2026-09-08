from odoo import fields, models


class CommissionPeriod(models.Model):
    _inherit = "commission.period"

    manager_seller_rule_ids = fields.One2many(
        "commission.manager.seller.rule",
        "period_id",
        string="Gestión administradores por vendedor",
    )
