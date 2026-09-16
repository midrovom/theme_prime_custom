import logging

_logger = logging.getLogger(__name__)


def _table_exists(cr, table):
    cr.execute(
        """
        SELECT 1
          FROM information_schema.tables
         WHERE table_schema = current_schema()
           AND table_name = %s
        """,
        (table,),
    )
    return bool(cr.fetchone())


def migrate(cr, version):
    """Verify the tables introduced by 18.0.1.3.0 after ORM sync."""
    required_tables = [
        "conedera_census_mobile_brand",
        "conedera_partner_mobile_brand_rel",
    ]
    missing = [table for table in required_tables if not _table_exists(cr, table)]
    if missing:
        raise RuntimeError(
            "Conedera 18.0.1.3.0 schema incomplete. Missing tables: %s"
            % ", ".join(missing)
        )
    _logger.info("Conedera 18.0.1.3.0: mobile brand schema verified")
