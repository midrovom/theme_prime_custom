from odoo import api, fields, models


class ErpRequestDepartment(models.Model):
    _name = "erp.request.department"
    _description = "Departamento solicitante"
    _order = "company_id, name"

    name = fields.Char(string="Departamento", required=True, index=True)

    customer_id = fields.Many2one(
        "res.partner",  
        string="Empresa cliente",
        required=True,
        index=True,
        ondelete="cascade",
    )
    manager_id = fields.Many2one(
        "res.users",
        string="Responsable del departamento",
        # domain="[('company_ids', 'in', company_id)]",
    )
    active = fields.Boolean(default=True)

    _sql_constraints = [
        (
            "erp_request_department_company_unique",
            "unique(name, customer_id)",
            "Ya existe un departamento con ese nombre en la empresa.",
        )
    ]

    @api.depends("name", "customer_id.name")
    def _compute_display_name(self):
        multi_company = len(self.env.companies) > 1
        for department in self:
            department.display_name = (
                f"{department.customer_id.name} / {department.name}"
                if multi_company
                else department.name
            )

