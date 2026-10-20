# -*- coding: utf-8 -*-
"""Conciliar gastos históricos al dejar de filtrar por subcentro.

No se modifican ni fechas, ni importes, ni códigos de subcentro originales.
Los gastos de cada cuenta/centro/mes/año se asignan a la primera línea
existente de esa combinación; así no se duplica Consumido si versiones
anteriores guardaron varias proyecciones para subcentros distintos.
"""
import logging
from collections import defaultdict

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    # Usar SQL para identificar coincidencias en un solo recorrido. Las
    # escrituras se hacen con ORM para recalcular los campos almacenados.
    cr.execute("""
        WITH canonical AS (
            SELECT DISTINCT ON (
                company_id, account_id, COALESCE(cost_center_id, 0), year, month
            ) id, company_id, account_id, cost_center_id, year, month
            FROM expense_budget_line
            ORDER BY company_id, account_id, COALESCE(cost_center_id, 0),
                     year, month, id
        )
        SELECT expense.id, selected_line.id
        FROM expense_budget_expense AS expense
        LEFT JOIN canonical AS selected_line
          ON selected_line.company_id = expense.company_id
         AND selected_line.account_id = expense.account_id
         AND selected_line.cost_center_id IS NOT DISTINCT FROM expense.cost_center_id
         AND selected_line.year = EXTRACT(YEAR FROM expense.date)::INTEGER
         AND selected_line.month = EXTRACT(MONTH FROM expense.date)::INTEGER::TEXT
        WHERE expense.budget_line_id IS DISTINCT FROM selected_line.id
    """)
    changes = defaultdict(list)
    for expense_id, target_line_id in cr.fetchall():
        changes[target_line_id or False].append(expense_id)

    Expense = env['expense.budget.expense'].sudo()
    changed = 0
    for target_id, expense_ids in changes.items():
        for start in range(0, len(expense_ids), 250):
            chunk = expense_ids[start:start + 250]
            Expense.browse(chunk).write({'budget_line_id': target_id})
            changed += len(chunk)
    if changed:
        _logger.info('[PRESUPUESTOS ERP] Migración 1.4.74: %s movimientos reconciliados ' 
                     'por cuenta/centro/mes/año sin filtrar subcentro', changed)
