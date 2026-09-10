import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Ensure every seller target uses the current stepwise sales-tier policy."""
    cr.execute(
        """
        UPDATE commission_seller_target
           SET calculation_mode = 'sales_tier',
               write_date = NOW()
         WHERE COALESCE(calculation_mode, '') <> 'sales_tier'
        """
    )
    _logger.info("Metas convertidas/normalizadas a rangos por venta: %s", cr.rowcount)
