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


def _relation_exists(cr, relation):
    cr.execute("SELECT to_regclass(%s)", [relation])
    return bool(cr.fetchone()[0])


def migrate(cr, version):
    # Repair columns before the new registry reads them. Idempotent by design.
    cr.execute("ALTER TABLE res_partner ADD COLUMN IF NOT EXISTS census_team_id integer")
    cr.execute("ALTER TABLE res_partner ADD COLUMN IF NOT EXISTS census_locked boolean DEFAULT FALSE")
    cr.execute("ALTER TABLE res_partner ADD COLUMN IF NOT EXISTS census_locked_at timestamp without time zone")
    cr.execute("ALTER TABLE res_partner ADD COLUMN IF NOT EXISTS census_unlock_user_id integer")
    cr.execute("ALTER TABLE res_partner ADD COLUMN IF NOT EXISTS census_unlock_until timestamp without time zone")

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
    for metric, sql in CHECKS.items():
        table = {
            "visits": "conedera_census_visit",
            "opening_hours": "conedera_partner_opening_hour",
            "business_rel": "conedera_partner_business_type_rel",
            "brand_rel": "conedera_partner_mobile_brand_rel",
        }.get(metric)
        if table and not _relation_exists(cr, table):
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
            ["18.0.1.7.0", metric, value],
        )
        _logger.info("Conedera 1.7 data guard PRE %s=%s", metric, value)
