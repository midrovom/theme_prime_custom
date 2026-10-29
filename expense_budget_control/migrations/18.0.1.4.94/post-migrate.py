# -*- coding: utf-8 -*-
"""Recompute stored consumptions and balances using original expense values.

The source API should be synchronized again after upgrading if amounts were
previously rounded by the Monetary field; historical detail cannot be guessed.
"""
import logging
from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def _recompute_batches(env, model_name, field_names, limit=400):
    Model = env[model_name].sudo()
    last_id = 0
    count = 0
    while True:
        records = Model.search([('id', '>', last_id)], limit=limit, order='id')
        if not records:
            break
        last_id = records[-1].id
        for field in field_names:
            env.add_to_compute(Model._fields[field], records)
        Model._recompute_recordset()
        count += len(records)
    _logger.info('[PRESUPUESTOS 1.4.94] Recalculados %s registros de %s.', count, model_name)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    _recompute_batches(env, 'expense.budget.line', ['actual_amount', 'variance_amount'])
    _recompute_batches(env, 'expense.budget', ['actual_amount', 'variance_amount'])
