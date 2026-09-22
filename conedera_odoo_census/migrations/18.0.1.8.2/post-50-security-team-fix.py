import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    Team = env["crm.team"].with_context(active_test=False).sudo()
    User = env["res.users"].with_context(active_test=False).sudo()
    Partner = env["res.partner"].with_context(active_test=False).sudo()

    # 1) Technical Odoo teams must never be offered as Catastro sales teams.
    technical = Team.browse()
    for xmlid in ("sales_team.salesteam_website_sales", "sales_team.pos_sales_team"):
        rec = env.ref(xmlid, raise_if_not_found=False)
        if rec:
            technical |= rec
    if technical:
        technical.write({"census_enabled": False})

    # Enable actual commercial teams that already have a leader/member. Do not
    # overwrite an intentionally disabled team on later upgrades.
    candidates = Team.search([
        ("active", "=", True),
        ("id", "not in", technical.ids or [0]),
        "|", ("user_id", "!=", False), ("member_ids", "!=", False),
    ])
    # New column is null/false on some upgraded databases; existing practical teams
    # need to remain usable. This is a one-time migration for 1.8.2.
    candidates.filtered(lambda t: not t.census_enabled).write({"census_enabled": True})

    # 2) Repair historical assignments conservatively.  Never change an existing
    # salesperson unless it is empty; recover it from "Catastrado por" first.  A
    # missing/technical/disabled team is recalculated from that salesperson.
    census_partners = Partner.search([("census_active", "=", True)])
    for partner in census_partners:
        values = {}
        responsible = partner.user_id
        if not responsible and partner.census_user_id and not partner.census_user_id.share:
            responsible = partner.census_user_id
            values["user_id"] = responsible.id
        team = partner.census_team_id
        if responsible and (not team or not team.census_enabled or team in technical):
            valid_team = partner._default_census_team(responsible)
            values["census_team_id"] = valid_team.id or False
        elif team and (not team.census_enabled or team in technical):
            values["census_team_id"] = False
        if values:
            partner.write(values)

    # 3) Introduce explicit Catastro roles without taking access away from users
    # who already used the module before 1.8.2.
    group_user = env.ref("conedera_odoo_census.group_census_user")
    group_supervisor = env.ref("conedera_odoo_census.group_census_supervisor")
    group_manager = env.ref("conedera_odoo_census.group_census_manager")
    internal_users = User.search([("share", "=", False)])
    existing_sale_users = internal_users.filtered(lambda u: u._has_group("sales_team.group_sale_salesman"))
    existing_sale_users.write({"groups_id": [(4, group_user.id)]})

    existing_sale_managers = internal_users.filtered(lambda u: u._has_group("sales_team.group_sale_manager"))
    system_admins = internal_users.filtered(lambda u: u._has_group("base.group_system"))
    admin_users = existing_sale_managers | system_admins
    admin_users.write({"groups_id": [(4, group_manager.id)]})

    leader_ids = set(
        Team.search([
            ("census_enabled", "=", True),
            ("active", "=", True),
            ("user_id", "!=", False),
        ]).mapped("user_id").ids
    )
    if leader_ids:
        User.browse(list(leader_ids)).write({"groups_id": [(4, group_supervisor.id)]})

    _logger.info(
        "Conedera 1.8.2 roles migrated: %s commercials, %s supervisors, %s administrators; technical teams disabled=%s",
        len(existing_sale_users), len(leader_ids), len(admin_users), technical.mapped("name"),
    )
