import logging

_logger = logging.getLogger(__name__)


# These are all stored fields added by this module directly on res.partner.
# The migration is intentionally idempotent because previous failed upgrades may
# have left the database with only a subset of the columns.
PARTNER_COLUMNS = {
    "census_active": "boolean",
    "census_date": "timestamp without time zone",
    "census_user_id": "integer",
    "commercial_name": "varchar",
    "store_count": "integer",
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

# sale.order can also be read by website_sale and other modules. Repair its
# custom stored fields in the same pre phase for consistency.
SALE_ORDER_COLUMNS = {
    "census_originated": "boolean",
    "census_visit_id": "integer",
}


def _ensure_columns(cr, table, columns):
    for name, sql_type in columns.items():
        cr.execute(
            f'ALTER TABLE "{table}" ADD COLUMN IF NOT EXISTS "{name}" {sql_type}'
        )

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
            "Schema repair failed for %s; missing columns: %s"
            % (table, ", ".join(missing))
        )
    _logger.info("Verified %d Conedera columns on %s", len(columns), table)


def migrate(cr, version):
    _logger.warning(
        "Running Conedera schema repair before module load (installed version: %s)",
        version,
    )
    _ensure_columns(cr, "res_partner", PARTNER_COLUMNS)
    _ensure_columns(cr, "sale_order", SALE_ORDER_COLUMNS)
