# -*- coding: utf-8 -*-
"""Migrar los objetivos anuales guardados en líneas a la cabecera del presupuesto."""
import logging
from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    Line = env['expense.budget.line'].sudo()
    Target = env['expense.budget.annual.target'].sudo().with_context(allow_annual_target_migration=True)

    # Agrupar por compañía/año/cuenta/centro para no crear más de un objetivo
    # anual para la misma combinación heredada.
    groups = {}
    for line in Line.search([('annual_amount', '>', 0)], order='id asc'):
        if not line.budget_id or not line.account_id:
            continue
        key = (line.company_id.id, line.year, line.account_id.id, line.cost_center_id.id or False)
        groups.setdefault(key, []).append(line)

    created = 0
    skipped = 0
    for (company_id, year, account_id, center_id), lines in groups.items():
        if Target.search_count([
            ('company_id', '=', company_id), ('year', '=', year),
            ('account_id', '=', account_id), ('cost_center_id', '=', center_id),
        ]):
            continue
        account = env['expense.budget.account'].browse(account_id).exists()
        if not account:
            skipped += 1
            continue
        # Prefer the budget of the account's actual rubric. A compatible legacy
        # header without a category is used only when no normal budget exists.
        budget = env['expense.budget'].search([
            ('company_id', '=', company_id), ('year', '=', year),
            ('category_id', '=', account.category_id.id),
        ], limit=1)
        if not budget:
            budget = next((line.budget_id for line in reversed(lines)
                           if not line.budget_id.category_id or line.budget_id.category_id == account.category_id), False)
        if not budget:
            skipped += 1
            _logger.warning(
                '[PRESUPUESTO 1.4.85] No se migró objetivo anual account=%s center=%s year=%s: no hay cabecera compatible.',
                account_id, center_id, year,
            )
            continue
        # Prefer the latest approved value; otherwise use the latest stored value.
        candidates = sorted(lines, key=lambda line: (line.approval_state == 'approved', line.id))
        amount = candidates[-1].annual_amount
        Target.create({
            'budget_id': budget.id,
            'account_id': account_id,
            'cost_center_id': center_id or False,
            'annual_amount': amount,
        })
        created += 1

    _logger.info('[PRESUPUESTO 1.4.85] Objetivos anuales migrados: %s; omitidos: %s.', created, skipped)
