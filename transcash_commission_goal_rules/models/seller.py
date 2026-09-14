from odoo import api, fields, models


class CommissionSeller(models.Model):
    _inherit = "commission.seller"

    is_corporate_project = fields.Boolean(
        string="Proyecto corporativo",
        help=(
            "Marque esta opción para vendedores de proyectos corporativos que deben "
            "liquidarse como un vendedor normal por su meta global y rangos. No se "
            "les calcula la comisión de proyecto por origen; el PDF los presenta en "
            "una sección independiente."
        ),
    )
    commission_report_group = fields.Selection(
        [
            ("retail", "Vendedores retail"),
            ("project", "Vendedores de proyectos"),
            ("corporate_project", "Proyectos corporativos"),
            ("manager", "Administradores"),
        ],
        string="Grupo de liquidación",
        compute="_compute_commission_report_group",
        store=True,
        index=True,
    )

    @api.depends("role", "is_corporate_project")
    def _compute_commission_report_group(self):
        for seller in self:
            if seller.is_corporate_project:
                seller.commission_report_group = "corporate_project"
            elif seller.role == "project":
                seller.commission_report_group = "project"
            elif seller.role in ("manager", "hybrid"):
                seller.commission_report_group = "manager"
            else:
                seller.commission_report_group = "retail"
