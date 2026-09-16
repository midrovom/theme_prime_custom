import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    expected = {
        "conedera_census_commercial_timeline",
        "conedera_census_product_quote_summary",
        "conedera_census_product_quote_line",
    }
    cr.execute(
        """
        SELECT table_name
          FROM information_schema.views
         WHERE table_schema = current_schema()
           AND table_name = ANY(%s)
        """,
        [list(expected)],
    )
    found = {row[0] for row in cr.fetchall()}
    missing = expected - found
    if missing:
        raise RuntimeError(
            "Conedera 18.0.1.4.0: faltan vistas SQL de análisis: %s"
            % ", ".join(sorted(missing))
        )
    _logger.info("Conedera 18.0.1.4.0: vistas de bitácora y productos verificadas")
