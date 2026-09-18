import logging

_logger = logging.getLogger(__name__)

VERSION = "18.0.1.8.1"
CHECKS = {
    "census_partners": ("res_partner", "SELECT COUNT(*) FROM res_partner WHERE COALESCE(census_active, FALSE) IS TRUE"),
    "visits": ("conedera_census_visit", "SELECT COUNT(*) FROM conedera_census_visit"),
    "opening_hours": ("conedera_partner_opening_hour", "SELECT COUNT(*) FROM conedera_partner_opening_hour"),
    "business_rel": ("conedera_partner_business_type_rel", "SELECT COUNT(*) FROM conedera_partner_business_type_rel"),
    "brand_rel": ("conedera_partner_mobile_brand_rel", "SELECT COUNT(*) FROM conedera_partner_mobile_brand_rel"),
    "census_sale_orders": ("sale_order", "SELECT COUNT(*) FROM sale_order WHERE COALESCE(census_originated, FALSE) IS TRUE"),
    "unlock_requests": ("conedera_census_unlock_request", "SELECT COUNT(*) FROM conedera_census_unlock_request"),
    "reassignment_requests": ("conedera_census_reassignment_request", "SELECT COUNT(*) FROM conedera_census_reassignment_request"),
    "visit_photos": (
        "ir_attachment",
        "SELECT COUNT(*) FROM ir_attachment WHERE res_model='conedera.census.visit' AND res_field='photo' AND res_id IS NOT NULL",
    ),
}


def migrate(cr, version):
    for metric, (_relation, sql) in CHECKS.items():
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
        _logger.info("Conedera 1.8.1 data guard POST %s=%s (before=%s)", metric, after, before)

    # Report historical duplicate active identities without modifying/deleting them.
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
            "Conedera 1.8.1 detectó %s identificaciones con más de un Catastro activo. "
            "No se eliminó nada; deben depurarse administrativamente.",
            len(duplicates),
        )
