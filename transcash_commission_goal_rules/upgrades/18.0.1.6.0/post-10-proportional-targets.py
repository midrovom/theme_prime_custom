import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Convert legacy seller targets to the proportional business rule.

    The migration keeps historical tiers but derives the two parameters used by
    the new calculation:
    - minimum achievement = first tier with a positive commission;
    - full commission = tier applicable at 100%, falling back to the highest tier.

    This is intentionally a post-upgrade script so all extension columns already
    exist before the SQL runs.
    """
    cr.execute(
        """
        SELECT column_name
          FROM information_schema.columns
         WHERE table_name = 'commission_seller_target'
           AND column_name IN (
               'calculation_mode', 'minimum_achievement', 'full_commission_percent'
           )
        """
    )
    columns = {row[0] for row in cr.fetchall()}
    required = {
        "calculation_mode",
        "minimum_achievement",
        "full_commission_percent",
    }
    if not required.issubset(columns):
        _logger.warning(
            "No están disponibles todos los campos de comisión proporcional; "
            "se omite la migración de metas."
        )
        return

    cr.execute(
        """
        UPDATE commission_seller_target t
           SET minimum_achievement = COALESCE(
                   (
                       SELECT MIN(x.min_achievement)
                         FROM commission_seller_target_tier x
                        WHERE x.target_id = t.id
                          AND x.commission_percent > 0
                   ),
                   NULLIF(t.minimum_achievement, 0),
                   80.0
               ),
               full_commission_percent = CASE
                   WHEN COALESCE(t.full_commission_percent, 0) > 0
                   THEN t.full_commission_percent
                   ELSE COALESCE(
                       (
                           SELECT x.commission_percent
                             FROM commission_seller_target_tier x
                            WHERE x.target_id = t.id
                              AND 100.0 >= x.min_achievement
                              AND (
                                  COALESCE(x.max_achievement, 0) = 0
                                  OR 100.0 <= x.max_achievement
                              )
                            ORDER BY x.min_achievement DESC, x.id DESC
                            LIMIT 1
                       ),
                       (
                           SELECT x.commission_percent
                             FROM commission_seller_target_tier x
                            WHERE x.target_id = t.id
                            ORDER BY x.min_achievement DESC, x.id DESC
                            LIMIT 1
                       ),
                       0.0
                   )
               END,
               calculation_mode = 'proportional',
               write_date = NOW()
         WHERE COALESCE(t.calculation_mode, 'tier') <> 'proportional'
            OR COALESCE(t.full_commission_percent, 0) <= 0
        """
    )
    _logger.info(
        "Metas de vendedor convertidas/normalizadas a cálculo proporcional: %s",
        cr.rowcount,
    )
