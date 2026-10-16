# -*- coding: utf-8 -*-
"""Regresión del dashboard: mismos consumidos, filtros por año y empresa."""
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestExpenseBudgetDashboard(TransactionCase):
    def setUp(self):
        super().setUp()
        self.company = self.env.company
        self.category = self.env['expense.budget.category'].create({
            'name': 'Servicios dashboard', 'code': 'DASH-CAT-2048',
            'company_id': self.company.id,
        })
        self.account_a = self.env['expense.budget.account'].create({
            'name': 'Luz dashboard', 'code': 'DASH-A-2048',
            'company_id': self.company.id, 'category_id': self.category.id,
        })
        self.account_b = self.env['expense.budget.account'].create({
            'name': 'Agua dashboard', 'code': 'DASH-B-2048',
            'company_id': self.company.id, 'category_id': self.category.id,
        })
        budget = self.env['expense.budget'].create({
            'name': 'Análisis dashboard 2048', 'company_id': self.company.id,
            'year': 2048,
        })
        Line = self.env['expense.budget.line']
        Line.create({
            'budget_id': budget.id, 'account_id': self.account_a.id,
            'month': '1', 'planned_amount': 100,
            'manual_actual_amount': 20,
        })
        Line.create({
            'budget_id': budget.id, 'account_id': self.account_a.id,
            'month': '2', 'planned_amount': 300,
            'manual_actual_amount': 60,
        })
        Line.create({
            'budget_id': budget.id, 'account_id': self.account_b.id,
            'month': '2', 'planned_amount': 150,
            'manual_actual_amount': 30,
        })

    def test_monthly_consumption_matches_budget_lines(self):
        payload = self.env['expense.budget.dashboard'].get_dashboard_data(
            self.company.id, 2048,
        )
        accounts = {acc['id']: acc for acc in payload['accounts']}
        self.assertIn(self.account_a.id, accounts)
        self.assertIn(self.account_b.id, accounts)
        self.assertAlmostEqual(accounts[self.account_a.id]['months'][0], 20)
        self.assertAlmostEqual(accounts[self.account_a.id]['months'][1], 60)
        self.assertAlmostEqual(accounts[self.account_b.id]['months'][1], 30)
        self.assertEqual(len(accounts[self.account_a.id]['months']), 12)
        self.assertIn(2048, payload['years'])
        self.assertIn(self.category.id, [cat['id'] for cat in payload['categories']])

    def test_other_year_has_no_spending(self):
        payload = self.env['expense.budget.dashboard'].get_dashboard_data(
            self.company.id, 2047,
        )
        self.assertEqual(payload['accounts'], [])
