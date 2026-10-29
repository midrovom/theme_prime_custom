# -*- coding: utf-8 -*-
"""1.4.96: saldos netos exactos aunque haya líneas sobregiradas."""
from odoo.tests.common import TransactionCase, tagged
from ..models.amount_utils import exact_display, exact_difference


@tagged('post_install', '-at_install')
class TestDisponibleNeto1496(TransactionCase):

    def test_totales_sin_compensacion_artificial(self):
        company = self.env.company
        category = self.env['expense.budget.category'].create({
            'name': 'Rubro 1496', 'code': 'TEST-1496', 'company_id': company.id,
        })
        account = self.env['expense.budget.account'].create({
            'name': 'Cuenta 1496', 'code': 'CTA-1496',
            'category_id': category.id, 'company_id': company.id,
        })
        budget = self.env['expense.budget'].with_context(
            skip_expense_budget_consumption_on_save=True,
        ).create({
            'name': 'Prueba neta 1496', 'company_id': company.id,
            'category_id': category.id, 'year': 2096,
        })
        Line = self.env['expense.budget.line'].with_context(
            skip_expense_budget_consumption_on_save=True,
        )
        first = Line.create({
            'budget_id': budget.id, 'account_id': account.id,
            'month': '1', 'planned_amount': 6000.0,
            'manual_actual_amount': 1159.92,
        })
        second = Line.create({
            'budget_id': budget.id, 'account_id': account.id,
            'month': '2', 'planned_amount': 1800.0,
            'manual_actual_amount': 2962.82,
        })
        first.invalidate_recordset(['available_to_spend', 'variance_amount'])
        second.invalidate_recordset(['available_to_spend', 'variance_amount'])
        budget.invalidate_recordset([
            'planned_amount', 'actual_amount', 'available_to_spend', 'variance_amount',
        ])
        self.assertAlmostEqual(first.available_to_spend, 4840.08, places=6)
        self.assertAlmostEqual(second.available_to_spend, -1162.82, places=6)
        self.assertAlmostEqual(budget.planned_amount, 7800.0, places=6)
        self.assertAlmostEqual(budget.actual_amount, 4122.74, places=6)
        self.assertAlmostEqual(budget.available_to_spend, 3677.26, places=6)
        self.assertAlmostEqual(budget.variance_amount, budget.available_to_spend, places=6)
        self.assertEqual(exact_display(budget.available_to_spend, 2), '3,677.26')

    def test_decimales_adicionales_no_se_recortan(self):
        self.assertEqual(exact_difference(7800, 4122.7417), 3677.2583)
        self.assertEqual(exact_display(3677.2583, 2), '3,677.2583')
