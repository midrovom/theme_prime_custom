# -*- coding: utf-8 -*-
"""Reconocer el rubro de presupuestos anteriores de forma NO destructiva.

El modelo histórico podía tener presupuesto sin rubro en cabecera y líneas con
varios rubros. Solo asignar un rubro cuando TODAS las cuentas del presupuesto
pertenecen al mismo rubro y no existe otro presupuesto con esa clave.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute("""
        SELECT b.id, MIN(a.category_id) AS category_id
          FROM expense_budget b
          JOIN expense_budget_line l ON l.budget_id = b.id
          JOIN expense_budget_account a ON a.id = l.account_id
         WHERE b.category_id IS NULL
         GROUP BY b.id
        HAVING COUNT(DISTINCT a.category_id) = 1
           AND COUNT(*) FILTER (WHERE a.category_id IS NULL) = 0
         ORDER BY b.id
    """)
    updated = 0
    skipped = 0
    for budget_id, category_id in cr.fetchall():
        cr.execute("""
            UPDATE expense_budget AS b
               SET category_id = %s
             WHERE b.id = %s AND b.category_id IS NULL
               AND EXISTS (
                   SELECT 1 FROM expense_budget_category c
                    WHERE c.id = %s AND c.company_id = b.company_id
               )
               AND NOT EXISTS (
                   SELECT 1 FROM expense_budget other
                    WHERE other.id != b.id
                      AND other.company_id = b.company_id
                      AND other.year = b.year
                      AND other.category_id = %s
               )
        """, (category_id, budget_id, category_id, category_id))
        if cr.rowcount:
            updated += 1
        else:
            skipped += 1
    _logger.info(
        '[PRESUPUESTOS RUBRO 1.4.79] Rúbrica histórica: %s cabeceras '
        'reconocidas, %s conservadas sin cambio por conflicto/empresa. '
        'Los históricos con varios rubros se conservan sin asignar.',
        updated, skipped,
    )
