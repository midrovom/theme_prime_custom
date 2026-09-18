import logging

_logger = logging.getLogger(__name__)

VERSION = "18.0.1.8.0"
CHECKS = {
    "census_partners": "SELECT COUNT(*) FROM res_partner WHERE COALESCE(census_active, FALSE) IS TRUE",
    "visits": "SELECT COUNT(*) FROM conedera_census_visit",
    "opening_hours": "SELECT COUNT(*) FROM conedera_partner_opening_hour",
    "business_rel": "SELECT COUNT(*) FROM conedera_partner_business_type_rel",
    "brand_rel": "SELECT COUNT(*) FROM conedera_partner_mobile_brand_rel",
    "census_sale_orders": "SELECT COUNT(*) FROM sale_order WHERE COALESCE(census_originated, FALSE) IS TRUE",
}


def migrate(cr, version):
    # The new reassignment model must exist after registry/model initialization.
    cr.execute("SELECT to_regclass('conedera_census_reassignment_request')")
    if not cr.fetchone()[0]:
        raise RuntimeError("Conedera 1.8: no se creó la tabla de solicitudes de reasignación")

    # Keep historical assignment metadata coherent without touching commercial history.
    cr.execute(
        """
        UPDATE res_partner
           SET user_id = census_user_id
         WHERE COALESCE(census_active, FALSE) IS TRUE
           AND user_id IS NULL
           AND census_user_id IS NOT NULL
        """
    )
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

    for metric, sql in CHECKS.items():
        cr.execute(
            "SELECT value FROM conedera_census_upgrade_guard WHERE version=%s AND metric=%s",
            [VERSION, metric],
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
        _logger.info("Conedera 1.8 data guard POST %s=%s (before=%s)", metric, after, before)

    # Report pre-existing duplicate active census identities without deleting/merging anything.
    cr.execute(
        """
        SELECT regexp_replace(upper(vat), '[^0-9A-Z]', '', 'g') AS key, COUNT(*)
          FROM res_partner
         WHERE COALESCE(census_active, FALSE) IS TRUE
           AND parent_id IS NULL
           AND vat IS NOT NULL
           AND regexp_replace(upper(vat), '[^0-9A-Z]', '', 'g') <> ''
         GROUP BY key
        HAVING COUNT(*) > 1
        """
    )
    duplicates = cr.fetchall()
    if duplicates:
        _logger.warning(
            "Conedera 1.8 detectó %s identificaciones con más de un Catastro activo. "
            "No se eliminó nada; esas fichas deben depurarse administrativamente.",
            len(duplicates),
        )
