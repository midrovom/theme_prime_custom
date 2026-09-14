import logging

from .models.client_utils import normalize_client_name

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    """Backfill selectable clients on first installation over historical sales."""
    cr = env.cr
    Client = env["commission.client"].sudo()

    cr.execute(
        """
        SELECT DISTINCT client
          FROM commission_sale
         WHERE NULLIF(BTRIM(client), '') IS NOT NULL
        """
    )
    raw_names = [row[0] for row in cr.fetchall()]
    linked_sales = 0
    for raw_name in raw_names:
        normalized = normalize_client_name(raw_name)
        if not normalized:
            continue
        client = Client.search([("normalized_name", "=", normalized)], limit=1)
        if not client:
            client = Client.create({
                "name": str(raw_name).strip(),
                "created_from_sales": True,
            })
        cr.execute(
            """
            UPDATE commission_sale
               SET client_id = %s,
                   client_match_name = %s,
                   write_uid = %s,
                   write_date = NOW()
             WHERE client = %s
               AND (client_id IS NULL OR client_match_name IS DISTINCT FROM %s)
            """,
            (client.id, normalized, env.uid, raw_name, normalized),
        )
        linked_sales += cr.rowcount

    # Compatibility with exclusions created by previous releases, if any.
    cr.execute("SELECT to_regclass('public.commission_period_client_exclusion')")
    if cr.fetchone()[0]:
        cr.execute(
            """
            SELECT id, client_name
              FROM commission_period_client_exclusion
             WHERE client_id IS NULL
               AND NULLIF(BTRIM(client_name), '') IS NOT NULL
            """
        )
        for exclusion_id, raw_name in cr.fetchall():
            client = Client.get_or_create_from_sale(raw_name)
            if client:
                cr.execute(
                    """
                    UPDATE commission_period_client_exclusion
                       SET client_id = %s,
                           client_name = %s,
                           normalized_client_name = %s,
                           write_uid = %s,
                           write_date = NOW()
                     WHERE id = %s
                    """,
                    (
                        client.id,
                        client.name,
                        client.normalized_name,
                        env.uid,
                        exclusion_id,
                    ),
                )

    _logger.info(
        "Post-init clientes de comisión: %s nombres históricos procesados, %s ventas enlazadas",
        len(raw_names),
        linked_sales,
    )
