import logging

_logger = logging.getLogger(__name__)

# Current persisted fields owned by this module on res.partner.
PARTNER_COLUMNS = {
    "census_active": "boolean",
    "census_date": "timestamp without time zone",
    "census_user_id": "integer",
    "commercial_name": "varchar",
    "census_store_count": "integer",
    "owner_contact_name": "varchar",
    "owner_phone": "varchar",
    "commercial_contact_name": "varchar",
    "commercial_contact_phone": "varchar",
    "business_description": "varchar",
    "customer_segment": "varchar",
    "business_type": "varchar",
    "customer_census_type": "varchar",
    "capa": "double precision",
    "census_gps_payload": "varchar",
    "census_gps_accuracy": "double precision",
    "census_gps_captured_at": "timestamp without time zone",
}

SALE_ORDER_COLUMNS = {
    "census_originated": "boolean",
    "census_visit_id": "integer",
}


def _ensure_columns(cr, table, columns):
    for name, sql_type in columns.items():
        cr.execute(f'ALTER TABLE "{table}" ADD COLUMN IF NOT EXISTS "{name}" {sql_type}')
    cr.execute(
        """
        SELECT column_name
          FROM information_schema.columns
         WHERE table_schema = current_schema()
           AND table_name = %s
           AND column_name = ANY(%s)
        """,
        [table, list(columns)],
    )
    present = {row[0] for row in cr.fetchall()}
    missing = sorted(set(columns) - present)
    if missing:
        raise RuntimeError(
            "Conedera schema repair failed for %s; missing columns: %s"
            % (table, ", ".join(missing))
        )


def migrate(cr, version):
    _logger.warning(
        "Running Conedera 18.0.1.2.0 schema repair (installed version: %s)", version
    )
    _ensure_columns(cr, "res_partner", PARTNER_COLUMNS)
    _ensure_columns(cr, "sale_order", SALE_ORDER_COLUMNS)

    # Migrate the old generic column if it exists. The new prefixed field avoids
    # collisions with third-party modules that may also define `store_count`.
    cr.execute(
        """
        SELECT 1
          FROM information_schema.columns
         WHERE table_schema = current_schema()
           AND table_name = 'res_partner'
           AND column_name = 'store_count'
        """
    )
    if cr.fetchone():
        cr.execute(
            """
            UPDATE res_partner
               SET census_store_count = CASE
                   WHEN COALESCE(store_count, 0) > 0 THEN store_count
                   WHEN census_active IS TRUE THEN 1
                   ELSE census_store_count
               END
             WHERE census_store_count IS NULL OR census_store_count = 0
            """
        )
    else:
        _logger.info("Legacy store_count column not present; store count remains pending when unknown")
