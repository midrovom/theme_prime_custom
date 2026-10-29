# -*- coding: utf-8 -*-
"""Regresión de precisión y captura sin importes precargados."""
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestBudgetDecimalPrecision1490(TransactionCase):

    def setUp(self):
        super().setUp()
        self.precision = self.env.ref('expense_budget_control.expense_budget_amount_precision')
        self.old_precision = self.precision.digits

    def tearDown(self):
        self.precision.sudo().write({'digits': self.old_precision})
        super().tearDown()

    def test_default_capture_starts_at_zero(self):
        defaults = self.env['expense.budget'].default_get(['quick_annual_amount'])
        self.assertEqual(defaults['quick_annual_amount'], 0.0)

    def test_precision_affects_distribution_without_changing_currency(self):
        line_model = self.env['expense.budget.line']
        original_currency_digits = self.env.company.currency_id.decimal_places
        self.precision.sudo().write({'digits': 2})
        self.assertEqual(line_model._monthly_amount_from_annual(1200, months_count=12), 100.0)
        self.assertEqual(line_model._monthly_amount_from_annual(1, months_count=3), 0.33)
        self.precision.sudo().write({'digits': 4})
        self.assertEqual(line_model._monthly_amount_from_annual(1, months_count=3), 0.3333)
        self.precision.sudo().write({'digits': 6})
        self.assertEqual(line_model._monthly_amount_from_annual(1, months_count=3), 0.333333)
        self.assertEqual(self.env.company.currency_id.decimal_places, original_currency_digits)

    def test_precision_settings_only_for_budget_manager(self):
        self.precision.sudo().write({'digits': 2})
        wizard = self.env['expense.budget.decimal.settings'].create({'digits': '6'})
        wizard.action_save()
        self.assertEqual(self.precision.digits, 6)
