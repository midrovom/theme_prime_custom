from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError

from .census_security_utils import (
    CENSUS_MANAGER_GROUP,
    CENSUS_SUPERVISOR_GROUP,
    CENSUS_USER_GROUP,
    is_census_manager,
)


class ConederaCensusRoleWizard(models.TransientModel):
    _name = "conedera.census.role.wizard"
    _description = "Asignar rol de Catastro"

    user_id = fields.Many2one(
        "res.users",
        string="Usuario",
        required=True,
        domain=[("share", "=", False), ("active", "=", True)],
    )
    role = fields.Selection(
        [
            ("none", "Sin acceso al Catastro"),
            ("user", "Comercial"),
            ("supervisor", "Supervisor"),
            ("manager", "Administrador"),
        ],
        string="Rol de Catastro",
        required=True,
        default="user",
    )
    current_role = fields.Char(string="Rol actual", compute="_compute_current_role")
    company_id = fields.Many2one(
        "res.company", string="Empresa", required=True, default=lambda self: self.env.company,
        domain=lambda self: [("id", "in", self.env.companies.ids)],
    )
    team_id = fields.Many2one(
        "crm.team",
        string="Equipo comercial",
        domain=[("census_enabled", "=", True), ("active", "=", True)],
        help="Equipo comercial que usará el usuario en Catastro. Los equipos técnicos de Sitio web/Punto de Venta no se muestran.",
    )
    help_text = fields.Html(
        string="Alcance",
        compute="_compute_help_text",
        sanitize=True,
    )

    @api.depends("user_id", "user_id.groups_id")
    def _compute_current_role(self):
        for wizard in self:
            user = wizard.user_id
            if not user:
                wizard.current_role = "—"
            elif user.has_group(CENSUS_MANAGER_GROUP):
                wizard.current_role = _("Administrador")
            elif user.has_group(CENSUS_SUPERVISOR_GROUP):
                wizard.current_role = _("Supervisor")
            elif user.has_group(CENSUS_USER_GROUP):
                wizard.current_role = _("Comercial")
            else:
                wizard.current_role = _("Sin acceso")

    @api.depends("role")
    def _compute_help_text(self):
        descriptions = {
            "none": _("<b>Sin acceso:</b> no verá el menú Catastro Comercial."),
            "user": _("<b>Comercial:</b> ve sus catastros, registra visitas/proformas y solicita cambios."),
            "supervisor": _("<b>Supervisor:</b> ve los catastros de los equipos que lidera y aprueba solicitudes. Debe estar configurado como líder del Equipo comercial."),
            "manager": _("<b>Administrador:</b> ve todos los catastros y administra configuración, equipos y permisos."),
        }
        for wizard in self:
            wizard.help_text = descriptions.get(wizard.role, "")

    @api.onchange("user_id")
    def _onchange_user_id(self):
        user = self.user_id
        if not user:
            return
        if user.company_id and user.company_id in self.env.companies:
            self.company_id = user.company_id
        if user.has_group(CENSUS_MANAGER_GROUP):
            self.role = "manager"
        elif user.has_group(CENSUS_SUPERVISOR_GROUP):
            self.role = "supervisor"
        elif user.has_group(CENSUS_USER_GROUP):
            self.role = "user"
        else:
            self.role = "none"

        Team = self.env["crm.team"].sudo().with_context(active_test=True)
        technical_ids = Team._census_technical_team_ids() if hasattr(Team, "_census_technical_team_ids") else set()
        teams = Team.search([
            ("census_enabled", "=", True),
            ("active", "=", True),
            ("company_id", "=", (self.company_id or self.env.company).id),
            "|", ("user_id", "=", user.id), ("member_ids", "in", [user.id]),
        ])
        if technical_ids:
            teams = teams.filtered(lambda team: team.id not in technical_ids)
        self.team_id = teams[:1]

    def action_apply(self):
        self.ensure_one()
        if not is_census_manager(self.env.user):
            raise AccessError(_("Solo un Administrador de Catastro puede asignar roles."))
        if not self.user_id or self.user_id.share:
            raise UserError(_("Seleccione un usuario interno activo."))

        user = self.user_id.sudo()
        groups = {
            "user": self.env.ref(CENSUS_USER_GROUP),
            "supervisor": self.env.ref(CENSUS_SUPERVISOR_GROUP),
            "manager": self.env.ref(CENSUS_MANAGER_GROUP),
        }
        all_group_ids = [group.id for group in groups.values()]

        # Remove only the three Catastro roles.  Other Odoo permissions are untouched.
        commands = [(3, group_id) for group_id in all_group_ids]
        if self.role in groups:
            commands.append((4, groups[self.role].id))
        user.write({"groups_id": commands})

        if self.role in ("user", "supervisor"):
            if not self.team_id:
                raise UserError(_("Seleccione un Equipo comercial habilitado para este usuario."))
            team = self.team_id.sudo()
            technical_ids = team._census_technical_team_ids() if hasattr(team, "_census_technical_team_ids") else set()
            if team.id in technical_ids or not team.census_enabled or not team.active:
                raise UserError(_("El equipo seleccionado no es válido para Catastro Comercial."))
            if not team.company_id or team.company_id != self.company_id:
                raise UserError(_("El Equipo comercial debe pertenecer a la Empresa seleccionada."))
            if team.company_id not in user.company_ids:
                raise UserError(_("El usuario no tiene acceso a la compañía del Equipo comercial seleccionado."))
            if self.role == "supervisor":
                team.write({"user_id": user.id})
            if user != team.user_id and user not in team.member_ids:
                team.write({"member_ids": [(4, user.id)]})

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Permisos actualizados"),
                "message": _("%s ahora tiene el rol: %s") % (user.name, dict(self._fields["role"].selection).get(self.role)),
                "type": "success",
                "sticky": False,
                "next": {"type": "ir.actions.act_window_close"},
            },
        }
