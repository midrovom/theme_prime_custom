import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Normaliza los campos de cumplimiento legados de los rangos de vendedor.

    Desde 18.0.1.6.0 el cálculo vigente usa sales_threshold. El módulo base,
    sin embargo, conserva min_achievement como obligatorio. Esta migración
    garantiza valores numéricos válidos para cualquier fila histórica.
    """
    cr.execute(
        """
        SELECT column_name
          FROM information_schema.columns
         WHERE table_name = 'commission_seller_target_tier'
           AND column_name IN ('min_achievement', 'max_achievement')
        """
    )
    columns = {row[0] for row in cr.fetchall()}
    if 'min_achievement' not in columns:
        _logger.warning(
            "No existe commission_seller_target_tier.min_achievement; "
            "se omite normalización de campos legados."
        )
        return

    if 'max_achievement' in columns:
        cr.execute(
            """
            UPDATE commission_seller_target_tier
               SET min_achievement = COALESCE(min_achievement, 0.0),
                   max_achievement = COALESCE(max_achievement, 0.0),
                   write_date = NOW()
             WHERE min_achievement IS NULL
                OR max_achievement IS NULL
            """
        )
    else:
        cr.execute(
            """
            UPDATE commission_seller_target_tier
               SET min_achievement = COALESCE(min_achievement, 0.0),
                   write_date = NOW()
             WHERE min_achievement IS NULL
            """
        )
    _logger.info("Rangos legados normalizados: %s", cr.rowcount)
