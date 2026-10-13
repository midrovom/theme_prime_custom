# -*- coding: utf-8 -*-
"""Recalcular los indicadores mensuales almacenados en versiones anteriores.

En versiones previas la edición inversa de `actual_amount` compartía el
compute con saldo y ejecución; algunos valores podían quedar en cero después
de guardar. Esta migración actualiza solo los campos calculados, no cambia las
proyecciones, ajustes manuales ni los movimientos registrados por API/Excel.
"""
from odoo import api, SUPERUSER_ID


def _recompute_in_batches(env, model_name, names):
    Model = env[model_name].sudo()
    last_id = 0
    while True:
        records = Model.search([('id', '>', last_id)], order='id', limit=500)
        if not records:
            break
        last_id = records[-1].id
        for name in names:
            env.add_to_compute(Model._fields[name], records)
        records._recompute_recordset()


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    _recompute_in_batches(env, 'expense.budget.line', (
        'actual_amount', 'variance_amount', 'execution_percentage',
    ))
    _recompute_in_batches(env, 'expense.budget', (
        'planned_amount', 'actual_amount', 'variance_amount', 'execution_percentage',
    ))
