import logging

_logger = logging.getLogger(__name__)


def _column_exists(cr, table, column):
    cr.execute(
        """
        SELECT 1
          FROM information_schema.columns
         WHERE table_name = %s
           AND column_name = %s
        """,
        (table, column),
    )
    return bool(cr.fetchone())


def migrate(cr, version):
    """Crea el maestro seleccionable de clientes y enlaza datos históricos.

    Se apoya en las claves normalizadas ya almacenadas desde 1.10.0, evitando
    recalcular nombres y evitando recorrer todas las ventas mediante ORM.
    """
    cr.execute("SELECT to_regclass('public.commission_client')")
    if not cr.fetchone()[0]:
        _logger.warning("No existe commission_client; se omite migración de clientes.")
        return

    if not _column_exists(cr, "commission_sale", "client_match_name"):
        _logger.warning("No existe commission_sale.client_match_name; se omite migración.")
        return

    # Maestros desde ventas existentes. MIN(client) elige una representación
    # estable del mismo nombre normalizado y evita una inserción por transacción.
    cr.execute(
        """
        INSERT INTO commission_client
            (name, normalized_name, active, created_from_sales,
             create_uid, write_uid, create_date, write_date)
        SELECT MIN(NULLIF(BTRIM(client), '')),
               client_match_name,
               TRUE, TRUE, 1, 1, NOW(), NOW()
          FROM commission_sale
         WHERE client_match_name IS NOT NULL
           AND client_match_name <> ''
           AND NULLIF(BTRIM(client), '') IS NOT NULL
         GROUP BY client_match_name
        ON CONFLICT (normalized_name) DO NOTHING
        """
    )
    from_sales = cr.rowcount

    # Incluye exclusiones antiguas aunque el cliente ya no tenga ventas en el
    # período disponible actualmente.
    if _column_exists(cr, "commission_period_client_exclusion", "normalized_client_name"):
        cr.execute(
            """
            INSERT INTO commission_client
                (name, normalized_name, active, created_from_sales,
                 create_uid, write_uid, create_date, write_date)
            SELECT MIN(NULLIF(BTRIM(client_name), '')),
                   normalized_client_name,
                   TRUE, FALSE, 1, 1, NOW(), NOW()
              FROM commission_period_client_exclusion
             WHERE normalized_client_name IS NOT NULL
               AND normalized_client_name <> ''
               AND NULLIF(BTRIM(client_name), '') IS NOT NULL
             GROUP BY normalized_client_name
            ON CONFLICT (normalized_name) DO NOTHING
            """
        )
        from_exclusions = cr.rowcount
    else:
        from_exclusions = 0

    if _column_exists(cr, "commission_sale", "client_id"):
        cr.execute(
            """
            UPDATE commission_sale s
               SET client_id = c.id,
                   write_date = NOW()
              FROM commission_client c
             WHERE s.client_id IS NULL
               AND s.client_match_name = c.normalized_name
            """
        )
        linked_sales = cr.rowcount
    else:
        linked_sales = 0

    if _column_exists(cr, "commission_period_client_exclusion", "client_id"):
        cr.execute(
            """
            UPDATE commission_period_client_exclusion e
               SET client_id = c.id,
                   client_name = c.name,
                   write_date = NOW()
              FROM commission_client c
             WHERE e.client_id IS NULL
               AND e.normalized_client_name = c.normalized_name
            """
        )
        linked_exclusions = cr.rowcount
    else:
        linked_exclusions = 0

    linked_dashboard = 0
    if (
        _column_exists(cr, "commission_dashboard_line", "client_id")
        and _column_exists(cr, "commission_dashboard_line", "sale_id")
    ):
        cr.execute(
            """
            UPDATE commission_dashboard_line d
               SET client_id = s.client_id,
                   write_date = NOW()
              FROM commission_sale s
             WHERE d.client_id IS NULL
               AND d.sale_id = s.id
               AND s.client_id IS NOT NULL
            """
        )
        linked_dashboard = cr.rowcount

    _logger.info(
        "Migración clientes: %s desde ventas, %s desde exclusiones, "
        "%s ventas enlazadas, %s exclusiones enlazadas, %s líneas dashboard enlazadas",
        from_sales,
        from_exclusions,
        linked_sales,
        linked_exclusions,
        linked_dashboard,
    )
