"""Last applied dispatch dashboard filters, isolated by user and active companies.

No direct ACL is granted for this internal model.  The dashboard service checks
its dispatch-user permission before accessing these records with sudo().
"""
from odoo import fields, models


class DispatchDashboardState(models.Model):
    _name = "dispatch.dashboard.state"
    _description = "Últimos filtros aplicados en Análisis de despachos"

    user_id = fields.Many2one("res.users", required=True, index=True, ondelete="cascade")
    company_scope = fields.Char(required=True, index=True)
    filters_json = fields.Json(default=dict)
    board_id = fields.Many2one("dispatch.board", ondelete="set null")
    favorite_id = fields.Many2one("ir.filters", ondelete="set null")

    _sql_constraints = [
        ("dispatch_dashboard_state_user_scope_unique", "unique(user_id, company_scope)",
         "Ya existen filtros activos para este usuario y estas compañías."),
    ]
