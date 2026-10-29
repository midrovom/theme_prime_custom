# -*- coding: utf-8 -*-
"""Actualizar el disponible neto almacenado sin tocar los importes originales.

La versión anterior solo sumaba saldos positivos por línea; esta migración
obliga a recomputar los campos almacenados para todos los presupuestos.
"""
import logging
from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def _recompute(env, model_name, field, batch_size=400):
    Model = env[model_name].sudo()
    last_id = 0
    updated = 0
    while True:
        records = Model.search([('id', '>', last_id)], order='id', limit=batch_size)
        if not records:
            break
        last_id = records[-1].id
        env.add_to_compute(Model._fields[field], records)
        Model._recompute_recordset()
        updated += len(records)
    _logger.info('[PRESUPUESTOS 1.4.96] %s registros recalculados: %s', updated, model_name)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    _recompute(env, 'expense.budget.line', 'available_to_spend')
    _recompute(env, 'expense.budget', 'available_to_spend')
