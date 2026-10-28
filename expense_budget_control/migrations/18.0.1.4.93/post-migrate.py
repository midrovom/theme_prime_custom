# -*- coding: utf-8 -*-
"""Reconcile legacy draft projections with their authorized annual amount.

Never change approved/submitted lines or the annual amount. Historical
incomplete distributions are also left alone.
"""
import logging
from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    Target = env['expense.budget.annual.target'].sudo()
    targets = Target.search([
        ('budget_id.state', '=', 'draft'),
        ('annual_amount', '>', 0),
    ])
    for target in targets:
        target._rebalance_exact_distribution()
    _logger.info('[PRESUPUESTO 1.4.93] Revisadas %d distribuciones de presupuestos en borrador.', len(targets))
