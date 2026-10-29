# -*- coding: utf-8 -*-
"""Inicializar el estado de aprobación por línea para presupuestos existentes."""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    # Al instalar este cambio, todo el presupuesto que ya estaba aprobado se
    # considera aprobado por línea; los pendientes y rechazados conservan el
    # sentido que tenía el estado de su cabecera antes de la nueva lógica.
    cr.execute("""
        UPDATE expense_budget_line AS line
           SET approval_state = CASE budget.state
               WHEN 'approved' THEN 'approved'
               WHEN 'to_approve' THEN 'to_approve'
               WHEN 'rejected' THEN 'rejected'
               ELSE 'draft'
           END
          FROM expense_budget AS budget
         WHERE line.budget_id = budget.id
    """)
    _logger.info('[PRESUPUESTO 1.4.81] Inicializado estado de aprobación para %s líneas.', cr.rowcount)
