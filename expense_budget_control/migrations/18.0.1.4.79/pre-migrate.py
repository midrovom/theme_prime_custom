# -*- coding: utf-8 -*-
"""Evitar fallas opacas de índice si hay presupuestos duplicados heredados.

Nunca borrar ni unir presupuestos previos automáticamente: contienen importes,
proyecciones y conciliaciones de gastos que deben preservarse.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute("""
        SELECT company_id, year, category_id, array_agg(id ORDER BY id)
          FROM expense_budget
         WHERE category_id IS NOT NULL
         GROUP BY company_id, year, category_id
        HAVING COUNT(*) > 1
         LIMIT 5
    """)
    duplicates = cr.fetchall()
    if duplicates:
        _logger.error('Presupuestos previos con empresa/año/rubro repetidos: %s', duplicates)
        raise RuntimeError(
            'No se puede actualizar expense_budget_control a 18.0.1.4.79: '
            'hay presupuestos existentes con la misma empresa, año y rubro. '
            'Revise los IDs indicados en el log y resuelva los duplicados '
            'sin perder sus líneas antes de actualizar. Conflictos: %s' % duplicates
        )
