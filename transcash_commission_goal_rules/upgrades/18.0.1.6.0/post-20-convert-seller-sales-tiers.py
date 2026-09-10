import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Convierte la configuración anterior a rangos por monto de ventas.

    - Rangos antiguos por % de cumplimiento: el mínimo se transforma a monto
      usando meta * porcentaje / 100.
    - Configuración proporcional sin rangos: crea dos escalones equivalentes
      (mínimo y 100%) como punto de partida para que el usuario los ajuste.
    - Finalmente deja todas las metas en modo sales_tier.

    Es una migración post para ejecutarse después de crear sales_threshold.
    """
    cr.execute(
        """
        SELECT 1
          FROM information_schema.columns
         WHERE table_name = 'commission_seller_target_tier'
           AND column_name = 'sales_threshold'
        """
    )
    if not cr.fetchone():
        _logger.warning(
            "No existe commission_seller_target_tier.sales_threshold; "
            "se omite conversión de rangos de vendedor."
        )
        return

    # Convierte rangos existentes basados en porcentaje de cumplimiento.
    cr.execute(
        """
        UPDATE commission_seller_target_tier tier
           SET sales_threshold = ROUND(
                   (target.target_amount * COALESCE(tier.min_achievement, 0.0) / 100.0)::numeric,
                   4
               ),
               write_uid = 1,
               write_date = NOW()
          FROM commission_seller_target target
         WHERE tier.target_id = target.id
           AND COALESCE(target.calculation_mode, 'tier') IN ('tier', 'proportional')
           AND COALESCE(tier.sales_threshold, 0.0) = 0.0
           AND COALESCE(tier.min_achievement, 0.0) > 0.0
        """
    )
    converted_tiers = cr.rowcount

    # Para metas proporcionales que no tenían líneas, genera escalones iniciales:
    # mínimo de elegibilidad y 100% de la meta. Así no se pierde la referencia
    # anterior, pero desde esta versión la lógica pasa a ser escalonada.
    cr.execute(
        """
        INSERT INTO commission_seller_target_tier
            (target_id, min_achievement, max_achievement, commission_percent,
             sales_threshold, create_uid, write_uid, create_date, write_date)
        SELECT
            target.id,
            COALESCE(target.minimum_achievement, 0.0),
            0.0,
            COALESCE(target.full_commission_percent, 0.0)
                * COALESCE(target.minimum_achievement, 0.0) / 100.0,
            ROUND(
                (target.target_amount * COALESCE(target.minimum_achievement, 0.0) / 100.0)::numeric,
                4
            ),
            1, 1, NOW(), NOW()
          FROM commission_seller_target target
         WHERE target.calculation_mode = 'proportional'
           AND NOT EXISTS (
                SELECT 1
                  FROM commission_seller_target_tier tier
                 WHERE tier.target_id = target.id
           )
        """
    )
    inserted_minimum = cr.rowcount

    cr.execute(
        """
        INSERT INTO commission_seller_target_tier
            (target_id, min_achievement, max_achievement, commission_percent,
             sales_threshold, create_uid, write_uid, create_date, write_date)
        SELECT
            target.id,
            100.0,
            0.0,
            COALESCE(target.full_commission_percent, 0.0),
            ROUND(target.target_amount::numeric, 4),
            1, 1, NOW(), NOW()
          FROM commission_seller_target target
         WHERE target.calculation_mode = 'proportional'
           AND COALESCE(target.minimum_achievement, 0.0) < 100.0
           AND NOT EXISTS (
                SELECT 1
                  FROM commission_seller_target_tier tier
                 WHERE tier.target_id = target.id
                   AND ABS(COALESCE(tier.sales_threshold, 0.0) - target.target_amount) < 0.0001
           )
        """
    )
    inserted_full = cr.rowcount

    cr.execute(
        """
        UPDATE commission_seller_target
           SET calculation_mode = 'sales_tier',
               write_uid = 1,
               write_date = NOW()
         WHERE COALESCE(calculation_mode, '') <> 'sales_tier'
        """
    )
    converted_targets = cr.rowcount

    _logger.info(
        "Rangos de vendedor convertidos: %s rangos existentes, %s escalones mínimos, "
        "%s escalones 100%%, %s metas en modo rangos por ventas.",
        converted_tiers,
        inserted_minimum,
        inserted_full,
        converted_targets,
    )
