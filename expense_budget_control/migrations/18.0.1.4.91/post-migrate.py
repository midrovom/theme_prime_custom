# -*- coding: utf-8 -*-
"""Restaurar orden calendario para las líneas históricas al actualizar."""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    # Columna nueva, calculada y almacenada: Odoo suele programar su
    # recomputación; el UPDATE también garantiza que los registros viejos se
    # ordenen correctamente inmediatamente tras actualizar el módulo.
    cr.execute("""
        UPDATE expense_budget_line
           SET month_number = CAST(month AS INTEGER)
         WHERE month IN ('1','2','3','4','5','6','7','8','9','10','11','12')
           AND month_number IS DISTINCT FROM CAST(month AS INTEGER)
    """)
    _logger.info('[PRESUPUESTO 1.4.91] Meses de las proyecciones históricos ordenados: %s', cr.rowcount)
