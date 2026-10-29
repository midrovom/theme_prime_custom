# -*- coding: utf-8 -*-
"""Regression: real consumption and available balance keep original decimals."""
from odoo.tests.common import TransactionCase, tagged
from ..models.amount_utils import exact_sum, exact_difference, exact_display


@tagged('post_install', '-at_install')
class TestNoRounding1494(TransactionCase):

    def test_decimal_helpers_and_formatting(self):
        self.assertEqual(exact_sum([0.1, 0.2, 0.0001]), 0.3001)
        self.assertEqual(exact_difference(10, 0.3001), 9.6999)
        self.assertEqual(exact_display(0.3001, 2), '0.3001')
        self.assertEqual(exact_display(100, 2), '100.00')
        self.assertEqual(exact_display(3.1, 4), '3.1000')

    def test_imported_expense_and_available_are_not_currency_rounded(self):
        company = self.env.company
        year = 2093
        category = self.env['expense.budget.category'].create({
            'name': 'Rubro 1494', 'code': 'R1494', 'company_id': company.id,
        })
        account = self.env['expense.budget.account'].create({
            'name': 'Cuenta 1494', 'code': 'A1494', 'category_id': category.id,
            'company_id': company.id,
        })
        budget = self.env['expense.budget'].with_context(
            skip_expense_budget_consumption_on_save=True,
        ).create({
            'name': 'Presupuesto sin redondear 1494', 'company_id': company.id,
            'year': year, 'category_id': category.id,
        })
        line = self.env['expense.budget.line'].with_context(
            skip_expense_budget_consumption_on_save=True,
        ).create({
            'budget_id': budget.id, 'account_id': account.id,
            'month': '1', 'planned_amount': 100,
        })
        Expense = self.env['expense.budget.expense']
        for index, value in enumerate((0.1234, 0.0056), start=1):
            Expense.create({
                'company_id': company.id, 'account_id': account.id,
                'budget_line_id': line.id, 'date': '%s-01-%02d' % (year, index),
                'amount': value, 'description': 'Movimiento de prueba %s' % index,
            })
        line.invalidate_recordset(['actual_amount', 'variance_amount'])
        self.assertAlmostEqual(line.actual_amount, 0.129, places=10)
        self.assertAlmostEqual(line.variance_amount, 99.871, places=10)
        budget.invalidate_recordset(['actual_amount', 'variance_amount'])
        self.assertAlmostEqual(budget.actual_amount, 0.129, places=10)
        self.assertAlmostEqual(budget.variance_amount, 99.871, places=10)
