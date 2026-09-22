from odoo import _, api, fields, models
from odoo.exceptions import UserError


class CrmTeam(models.Model):
    _inherit = "crm.team"

    census_enabled = fields.Boolean(
        string="Disponible para Catastro",
        default=False,
        help=(
            "Solo los equipos marcados aquí pueden asignarse a un Catastro. "
            "Esto evita seleccionar equipos técnicos como Sitio web o Punto de Venta."
        ),
    )

    def _census_technical_team_ids(self):
        ids = []
        for xmlid in ("sales_team.salesteam_website_sales", "sales_team.pos_sales_team"):
            record = self.env.ref(xmlid, raise_if_not_found=False)
            if record:
                ids.append(record.id)
        return set(ids)

    def _check_census_enable_allowed(self):
        technical_ids = self._census_technical_team_ids()
        blocked = self.filtered(lambda team: team.id in technical_ids)
        if blocked:
            raise UserError(
                _(
                    "El equipo técnico '%s' no puede usarse en Catastro Comercial. "
                    "Cree o seleccione un Equipo de Ventas comercial con líder y miembros."
                )
                % ", ".join(blocked.mapped("name"))
            )

    @api.constrains("census_enabled", "company_id")
    def _check_census_company(self):
        for team in self:
            if team.census_enabled and not team.company_id:
                raise UserError(_("Un Equipo habilitado para Catastro debe pertenecer a una empresa específica."))

    def write(self, vals):
        if vals.get("census_enabled"):
            self._check_census_enable_allowed()
        result = super().write(vals)
        self._check_census_company()
        return result
