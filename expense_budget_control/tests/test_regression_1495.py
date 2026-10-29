# -*- coding: utf-8 -*-
"""Regresión: disponible neto con signo, conservando exceso interno."""
from odoo.tests.common import TransactionCase, tagged
from ..models.amount_utils import exact_sum


@tagged('post_install', '-at_install')
class TestExceso1495(TransactionCase):

    def test_disponible_neto_y_exceso_interno(self):
        company = self.env.company
        category = self.env['expense.budget.category'].create({
            'name': 'Rubro test exceso', 'code': 'TEST-1495', 'company_id': company.id,
        })
        account = self.env['expense.budget.account'].create({
            'name': 'Agua test exceso', 'code': 'AGUA-1495',
            'company_id': company.id, 'category_id': category.id,
        })
        budget = self.env['expense.budget'].with_context(
            skip_expense_budget_consumption_on_save=True,
        ).create({
            'name': 'Test exceso 1495', 'company_id': company.id,
            'category_id': category.id, 'year': 2095,
        })
        Line = self.env['expense.budget.line'].with_context(
            skip_expense_budget_consumption_on_save=True,
        )
        february = Line.create({
            'budget_id': budget.id, 'account_id': account.id,
            'month': '2', 'planned_amount': 108.34,
            'manual_actual_amount': 149.41,
        })
        march = Line.create({
            'budget_id': budget.id, 'account_id': account.id,
            'month': '3', 'planned_amount': 200.0,
            'manual_actual_amount': 100.0,
        })
        february.invalidate_recordset(['variance_amount','available_to_spend','excess_amount'])
        self.assertAlmostEqual(february.variance_amount, -41.07, places=6)
        self.assertAlmostEqual(february.available_to_spend, -41.07, places=6)
        self.assertAlmostEqual(february.excess_amount, 41.07, places=6)
        march.invalidate_recordset(['variance_amount','available_to_spend','excess_amount'])
        self.assertAlmostEqual(march.available_to_spend, 100.0, places=6)
        self.assertAlmostEqual(march.excess_amount, 0.0, places=6)
        budget.invalidate_recordset(['variance_amount','available_to_spend','excess_amount'])
        self.assertAlmostEqual(budget.available_to_spend, 58.93, places=6)
        self.assertAlmostEqual(budget.excess_amount, 41.07, places=6)
        self.assertAlmostEqual(budget.variance_amount, 58.93, places=6)
        self.assertAlmostEqual(
            exact_sum((budget.planned_amount, -budget.actual_amount)),
            budget.available_to_spend, places=6,
        )
