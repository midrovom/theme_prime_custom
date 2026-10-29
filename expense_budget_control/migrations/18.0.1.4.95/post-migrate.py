# -*- coding: utf-8 -*-
"""Populate new stored positive balances/excess for pre-existing budgets.

Do not modify projected, actual or signed variance amounts: the signed amount
still feeds the cumulative closing and opening balance computations.
"""
import logging
from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def _recompute(env, model_name, names, batch_size=400):
    model = env[model_name].sudo()
    last_id = 0
    count = 0
    while True:
        records = model.search([('id', '>', last_id)], order='id', limit=batch_size)
        if not records:
            break
        last_id = records[-1].id
        for name in names:
            env.add_to_compute(model._fields[name], records)
        model._recompute_recordset()
        count += len(records)
    _logger.info('Presupuestos 1.4.95: recalculados %s registros en %s', count, model_name)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    _recompute(env, 'expense.budget.line', ['available_to_spend', 'excess_amount'])
    _recompute(env, 'expense.budget', ['available_to_spend', 'excess_amount'])
