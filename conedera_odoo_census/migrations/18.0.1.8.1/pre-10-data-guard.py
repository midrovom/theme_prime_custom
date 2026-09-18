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


def _relation_exists(cr, relation):
    cr.execute("SELECT to_regclass(%s)", [relation])
    return bool(cr.fetchone()[0])


def migrate(cr, version):
    cr.execute(
        """
        CREATE TABLE IF NOT EXISTS conedera_census_upgrade_guard (
            version varchar NOT NULL,
            metric varchar NOT NULL,
            value bigint NOT NULL,
            captured_at timestamp without time zone NOT NULL DEFAULT NOW(),
            PRIMARY KEY (version, metric)
        )
        """
    )
    for metric, (relation, sql) in CHECKS.items():
        if not _relation_exists(cr, relation):
            value = 0
        else:
            cr.execute(sql)
            value = cr.fetchone()[0]
        cr.execute(
            """
            INSERT INTO conedera_census_upgrade_guard(version, metric, value)
            VALUES (%s, %s, %s)
            ON CONFLICT (version, metric)
            DO UPDATE SET value = EXCLUDED.value, captured_at = NOW()
            """,
            [VERSION, metric, value],
        )
        _logger.info("Conedera 1.8.1 data guard PRE %s=%s", metric, value)
