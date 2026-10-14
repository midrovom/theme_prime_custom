# -*- coding: utf-8 -*-
"""Permitir cuentas sin rubro para su vinculación posterior en Presupuesto."""


def migrate(cr, version):
    cr.execute('ALTER TABLE expense_budget_account ALTER COLUMN category_id DROP NOT NULL')
