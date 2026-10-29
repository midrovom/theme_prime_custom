# -*- coding: utf-8 -*-
"""1.4.103: ejecución restaurada y disponible neto en cabecera."""
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestResumenPresupuesto14103(TransactionCase):

    def test_disponible_neto_y_ejecucion_sin_cambiar_formula(self):
        company = self.env.company
        category = self.env['expense.budget.category'].create({
            'name': 'Rubro 14103', 'code': 'TEST-14103', 'company_id': company.id,
        })
        account = self.env['expense.budget.account'].create({
            'name': 'Cuenta 14103', 'code': 'CTA-14103',
            'category_id': category.id, 'company_id': company.id,
        })
        budget = self.env['expense.budget'].with_context(
            skip_expense_budget_consumption_on_save=True,
        ).create({
            'name': 'Resumen 14103', 'company_id': company.id,
            'category_id': category.id, 'year': 2098,
        })
        line = self.env['expense.budget.line'].with_context(
            skip_expense_budget_consumption_on_save=True,
        ).create({
            'budget_id': budget.id, 'account_id': account.id,
            'month': '1', 'planned_amount': 6400.0,
            'manual_actual_amount': 40.55,
        })
        budget.invalidate_recordset([
            'planned_amount', 'actual_amount', 'available_to_spend', 'execution_percentage'
        ])
        self.assertAlmostEqual(budget.planned_amount, 6400.0, places=6)
        self.assertAlmostEqual(budget.actual_amount, 40.55, places=6)
        self.assertAlmostEqual(budget.available_to_spend, 6359.45, places=6)
        self.assertAlmostEqual(budget.execution_percentage, 0.63, places=2)
        self.assertEqual(self.env['expense.budget']._fields['available_to_spend'].string, 'Disponible neto')
        self.assertAlmostEqual(line.execution_percentage, 0.63, places=2)
