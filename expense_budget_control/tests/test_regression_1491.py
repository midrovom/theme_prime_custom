# -*- coding: utf-8 -*-
"""Regresión de la vista sin distribuciones y el orden cronológico de los meses."""
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestChronologicalMonths1491(TransactionCase):

    def test_month_order_is_numeric(self):
        Line = self.env['expense.budget.line']
        self.assertIn('month_number', Line._order)
        for value, expected in [('1', 1), ('2', 2), ('10', 10), ('11', 11), ('12', 12)]:
            line = Line.new({'month': value})
            line._compute_month_number()
            self.assertEqual(line.month_number, expected)

    def test_annual_targets_stay_in_model_but_tab_is_removed(self):
        Budget = self.env['expense.budget']
        self.assertIn('annual_target_ids', Budget._fields)
        view = self.env.ref('expense_budget_control.view_expense_budget_form')
        self.assertNotIn('page string="Distribuciones registradas"', view.arch_db)
        self.assertIn('default_order="month_number', view.arch_db)
