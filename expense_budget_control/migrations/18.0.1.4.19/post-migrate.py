# -*- coding: utf-8 -*-
"""Asignar a presupuestos antiguos el rubro de sus cuentas sin alterar nombres.

La selección del rubro es nueva: no debe ocultar los presupuestos que ya
estaban creados ni reescribir títulos históricos usados en impresiones.
"""


def migrate(cr, version):
    # Inferencia inequívoca: todas las líneas del presupuesto pertenecen
    # al mismo rubro y el rubro corresponde a la empresa del presupuesto.
    cr.execute("""
        UPDATE expense_budget AS b
           SET category_id = grouped.category_id
          FROM (
                SELECT l.budget_id, MIN(a.category_id) AS category_id
                  FROM expense_budget_line AS l
                  JOIN expense_budget_account AS a ON a.id = l.account_id
                 GROUP BY l.budget_id
                HAVING COUNT(DISTINCT a.category_id) = 1
               ) AS grouped
          JOIN expense_budget_category AS c ON c.id = grouped.category_id
         WHERE b.id = grouped.budget_id
           AND b.company_id = c.company_id
           AND b.category_id IS NULL
    """)
    # Sin líneas, únicamente si el nombre antiguo coincide con el único
    # rubro homónimo de la misma empresa.
    cr.execute("""
        UPDATE expense_budget AS b
           SET category_id = c.id
          FROM expense_budget_category AS c
         WHERE b.category_id IS NULL
           AND b.company_id = c.company_id
           AND LOWER(TRIM(b.name)) = LOWER(TRIM(c.name))
           AND NOT EXISTS (
                SELECT 1 FROM expense_budget_line AS l
                 WHERE l.budget_id = b.id
           )
    """)
