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
    for metric, sql in CHECKS.items():
        cr.execute(
            "SELECT value FROM conedera_census_upgrade_guard WHERE version=%s AND metric=%s",
            ["18.0.1.6.0", metric],
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
        _logger.info("Conedera data guard POST %s=%s (before=%s)", metric, after, before)

    # Explicit sanity checks for the analytical views used by mobile bitácora and products.
    expected_views = {
        "conedera_census_commercial_timeline",
        "conedera_census_product_quote_summary",
        "conedera_census_product_quote_line",
    }
    cr.execute(
        """
        SELECT table_name FROM information_schema.views
         WHERE table_schema=current_schema() AND table_name = ANY(%s)
        """,
        [list(expected_views)],
    )
    found = {r[0] for r in cr.fetchall()}
    missing = expected_views - found
    if missing:
        raise RuntimeError("Conedera: faltan vistas SQL: %s" % ", ".join(sorted(missing)))
