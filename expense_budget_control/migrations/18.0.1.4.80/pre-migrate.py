# -*- coding: utf-8 -*-
"""Quitar únicamente la antigua UNIQUE(empresa, año), si quedó instalada.

NO modificar las restricciones de rubro ni eliminar registros históricos.
"""
import logging
_logger = logging.getLogger(__name__)


def migrate(cr, version):
    # Algunas bases que migraron desde 1.4.3 conservaron esta restricción;
    # impediría presupuestos de rubros diferentes en el mismo año.
    cr.execute("""
        ALTER TABLE expense_budget
        DROP CONSTRAINT IF EXISTS expense_budget_year_company_unique
    """)
    _logger.info('[PRESUPUESTOS 1.4.80] Eliminada restricción antigua empresa/año (si existía).')
