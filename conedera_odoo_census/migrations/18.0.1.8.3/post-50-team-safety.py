import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    Team = env["crm.team"].with_context(active_test=False).sudo()
    Partner = env["res.partner"].with_context(active_test=False).sudo()

    technical = Team.browse()
    for xmlid in ("sales_team.salesteam_website_sales", "sales_team.pos_sales_team"):
        rec = env.ref(xmlid, raise_if_not_found=False)
        if rec:
            technical |= rec
    if technical:
        technical.write({"census_enabled": False})

    # Keep practical sales teams available. This does not touch team membership,
    # leader, customer ownership or any historical Catastro data.
    candidates = Team.search([
        ("active", "=", True),
        ("id", "not in", technical.ids or [0]),
        "|", ("user_id", "!=", False), ("member_ids", "!=", False),
    ])
    candidates.filtered(lambda team: not team.census_enabled).write({"census_enabled": True})

    # Repair only invalid technical/disabled team assignments. Preserve the
    # salesperson and all visits/quotes/history; recalculate from their memberships.
    repaired = 0
    for partner in Partner.search([("census_active", "=", True)]):
        team = partner.census_team_id
        if team and team.census_enabled and team not in technical:
            continue
        if partner.user_id:
            valid_team = partner._default_census_team(partner.user_id)
            if valid_team:
                cr.execute(
                    "UPDATE res_partner SET census_team_id=%s WHERE id=%s",
                    [valid_team.id, partner.id],
                )
                repaired += 1
            elif team:
                cr.execute(
                    "UPDATE res_partner SET census_team_id=NULL WHERE id=%s",
                    [partner.id],
                )
                repaired += 1
        elif team:
            cr.execute(
                "UPDATE res_partner SET census_team_id=NULL WHERE id=%s",
                [partner.id],
            )
            repaired += 1


    # Re-assert Catastro roles idempotently. This is intentionally additive: it
    # never removes groups from any other addon (including Ventas en Ruta).
    User = env["res.users"].with_context(active_test=False).sudo()
    group_user = env.ref("conedera_odoo_census.group_census_user")
    group_supervisor = env.ref("conedera_odoo_census.group_census_supervisor")
    group_manager = env.ref("conedera_odoo_census.group_census_manager")
    internal = User.search([("share", "=", False)])
    sales_users = internal.filtered(lambda u: u._has_group("sales_team.group_sale_salesman"))
    if sales_users:
        sales_users.write({"groups_id": [(4, group_user.id)]})
    sales_managers = internal.filtered(lambda u: u._has_group("sales_team.group_sale_manager"))
    system_admins = internal.filtered(lambda u: u._has_group("base.group_system"))
    if sales_managers | system_admins:
        (sales_managers | system_admins).write({"groups_id": [(4, group_manager.id)]})
    leaders = candidates.mapped("user_id").filtered(lambda u: u and not u.share)
    if leaders:
        leaders.write({"groups_id": [(4, group_supervisor.id)]})

    _logger.info(
        "Conedera 1.8.3 team safety: technical disabled=%s, repaired assignments=%s",
        technical.mapped("name"), repaired,
    )
