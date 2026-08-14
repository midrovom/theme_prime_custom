from odoo import api, fields, models


class ErpRequestDepartment(models.Model):
    _name = "erp.request.department"
    _description = "Departamento solicitante"
    _order = "partner_id, name"

    name = fields.Char(string="Departamento", required=True, index=True)

    partner_id = fields.Many2one(
        "res.partner",
        string="Empresa cliente",
        required=True,
        index=True,
        ondelete="cascade",
        domain="[('is_company', '=', True)]",
    )

    manager_id = fields.Many2one(
        "res.users",
        string="Responsable del departamento",
    )
    active = fields.Boolean(default=True)

    _sql_constraints = [
        (
            "erp_request_department_partner_unique",
            "unique(name, partner_id)",
            "Ya existe un departamento con ese nombre en la empresa cliente.",
        )
    ]

    @api.depends("name")
    def _compute_display_name(self):
        for department in self:
            department.display_name = department.name

