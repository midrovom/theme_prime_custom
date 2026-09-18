import logging

_logger = logging.getLogger(__name__)

CHECKS = {
    "census_partners": "SELECT COUNT(*) FROM res_partner WHERE COALESCE(census_active, FALSE) IS TRUE",
    "visits": "SELECT COUNT(*) FROM conedera_census_visit",
    "opening_hours": "SELECT COUNT(*) FROM conedera_partner_opening_hour",
    "business_rel": "SELECT COUNT(*) FROM conedera_partner_business_type_rel",
    "brand_rel": "SELECT COUNT(*) FROM conedera_partner_mobile_brand_rel",
    "census_sale_orders": "SELECT COUNT(*) FROM sale_order WHERE COALESCE(census_originated, FALSE) IS TRUE",
}


def migrate(cr, version):
    # Preserve visibility of historical catastros. Older builds normally filled
    # user_id, but if it is empty we recover the original census operator.
    cr.execute(
        """
        UPDATE res_partner
           SET user_id = census_user_id
         WHERE COALESCE(census_active, FALSE) IS TRUE
           AND user_id IS NULL
           AND census_user_id IS NOT NULL
        """
    )

    # Assign existing catastros to the salesperson's main Sales Team when possible.
    cr.execute(
        """
        UPDATE res_partner p
           SET census_team_id = u.sale_team_id
          FROM res_users u
         WHERE p.user_id = u.id
           AND COALESCE(p.census_active, FALSE) IS TRUE
           AND p.census_team_id IS NULL
           AND u.sale_team_id IS NOT NULL
        """
    )
    # Existing catastros are already registered business data: protect them after upgrade.
    cr.execute(
        """
        UPDATE res_partner
           SET census_locked = TRUE,
               census_locked_at = COALESCE(census_locked_at, NOW())
         WHERE COALESCE(census_active, FALSE) IS TRUE
        """
    )

    for metric, sql in CHECKS.items():
        cr.execute(
            "SELECT value FROM conedera_census_upgrade_guard WHERE version=%s AND metric=%s",
            ["18.0.1.7.0", metric],
        )
        row = cr.fetchone()
        before = row[0] if row else 0
        cr.execute(sql)
        after = cr.fetchone()[0]
        if after < before:
            raise RuntimeError(
                "Conedera aborta la actualización para proteger datos: %s bajó de %s a %s"
                % (metric, before, after)
            )
        _logger.info("Conedera 1.7 data guard POST %s=%s (before=%s)", metric, after, before)
