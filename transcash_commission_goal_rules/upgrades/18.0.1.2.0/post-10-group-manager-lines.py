import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Agrupa reglas antiguas por administrador/período/local.

    Se ejecuta en fase post, cuando Odoo ya creó la tabla cabecera y la nueva
    columna management_id en commission_manager_seller_rule. Esto evita el
    fallo UndefinedColumn que ocurría al hacerlo desde model.init().
    """
    cr.execute(
        """
        SELECT 1
          FROM information_schema.columns
         WHERE table_name = 'commission_manager_seller_rule'
           AND column_name = 'management_id'
        """
    )
    if not cr.fetchone():
        _logger.warning(
            "No existe commission_manager_seller_rule.management_id; "
            "se omite migración de gestión administrativa."
        )
        return

    cr.execute(
        """
        SELECT to_regclass('public.commission_manager_goal_rule')
        """
    )
    if not cr.fetchone()[0]:
        _logger.warning(
            "No existe commission_manager_goal_rule; se omite migración."
        )
        return

    # Crea una cabecera por combinación período + administrador + local.
    # NOT EXISTS hace la operación segura si ya existe alguna cabecera.
    cr.execute(
        """
        INSERT INTO commission_manager_goal_rule
            (period_id, manager_id, location_id, active,
             create_uid, write_uid, create_date, write_date)
        SELECT DISTINCT
            r.period_id, r.manager_id, r.location_id, TRUE,
            1, 1, NOW(), NOW()
          FROM commission_manager_seller_rule r
         WHERE r.management_id IS NULL
           AND r.period_id IS NOT NULL
           AND r.manager_id IS NOT NULL
           AND r.location_id IS NOT NULL
           AND NOT EXISTS (
                SELECT 1
                  FROM commission_manager_goal_rule g
                 WHERE g.period_id = r.period_id
                   AND g.manager_id = r.manager_id
                   AND g.location_id = r.location_id
           )
        """
    )
    created = cr.rowcount

    # Enlaza las líneas históricas a la cabecera correspondiente.
    cr.execute(
        """
        UPDATE commission_manager_seller_rule r
           SET management_id = g.id,
               write_uid = 1,
               write_date = NOW()
          FROM commission_manager_goal_rule g
         WHERE r.management_id IS NULL
           AND g.period_id = r.period_id
           AND g.manager_id = r.manager_id
           AND g.location_id = r.location_id
        """
    )
    linked = cr.rowcount

    _logger.info(
        "Migración gestión administradores: %s cabeceras creadas, %s líneas enlazadas",
        created, linked,
    )
