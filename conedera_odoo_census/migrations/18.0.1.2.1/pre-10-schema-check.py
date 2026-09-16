import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Defensive schema check for the store-count field.

    Previous installations may have been interrupted during upgrade. This step
    guarantees that the field used by the new readiness gate exists before the
    model is loaded. It is intentionally idempotent.
    """
    _logger.info("Conedera 18.0.1.2.1: checking census_store_count schema")
    cr.execute(
        'ALTER TABLE res_partner ADD COLUMN IF NOT EXISTS census_store_count integer'
    )

    # Preserve a value from the legacy generic field when that column exists.
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
               SET census_store_count = store_count
             WHERE COALESCE(census_store_count, 0) = 0
               AND COALESCE(store_count, 0) > 0
            """
        )
