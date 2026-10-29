# -*- coding: utf-8 -*-
"""Selector de año y prorrateo automático con meses opcionales."""
from datetime import date
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestQuickMonthFallback1489(TransactionCase):

    def setUp(self):
        super().setUp()
        self.company = self.env.company
        self.category = self.env['expense.budget.category'].create({
            'name': 'Rubro prueba 1489', 'code': 'RB-1489',
            'company_id': self.company.id,
        })
        self.account = self.env['expense.budget.account'].create({
            'name': 'Agua 1489', 'code': 'AG-1489',
            'category_id': self.category.id, 'company_id': self.company.id,
        })
        self.account2 = self.env['expense.budget.account'].create({
            'name': 'Electricidad 1489', 'code': 'EE-1489',
            'category_id': self.category.id, 'company_id': self.company.id,
        })
        self.center = self.env['expense.budget.cost.center'].create({
            'name': 'Quito 1489', 'code': 'QUI-1489',
            'company_id': self.company.id,
        })
        self.budget = self.env['expense.budget'].with_context(
            skip_expense_budget_consumption_on_save=True,
        ).create({
            'name': 'Presupuesto 1489', 'year': 2096,
            'category_id': self.category.id, 'company_id': self.company.id,
        })
        group = self.env.ref('expense_budget_control.group_expense_budget_registrar')
        self.registrar = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Registro 1489', 'login': 'registro_1489_presupuesto',
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id, group.id])],
            'company_id': self.company.id,
            'company_ids': [(6, 0, [self.company.id])],
        })

    def _add(self, account, amount, months=False):
        budget = self.budget.with_user(self.registrar).with_context(
            skip_expense_budget_consumption_on_save=True,
        )
        budget.write({
            'quick_account_id': account.id,
            'quick_cost_center_id': self.center.id,
            'quick_annual_amount': amount,
            'quick_month_ids': [(6, 0, months.ids)] if months else [(5, 0, 0)],
        })
        budget.action_add_quick_monthly_lines()
        return self.budget.line_ids.filtered(lambda line: line.account_id == account)

    def test_no_month_selected_creates_twelve(self):
        lines = self._add(self.account, 1200)
        self.assertEqual(len(lines), 12)
        self.assertEqual({int(item.month) for item in lines}, set(range(1, 13)))
        self.assertTrue(all(item.planned_amount == 100 for item in lines))
        self.assertFalse(self.budget.quick_account_id)
        self.assertFalse(self.budget.quick_cost_center_id)
        self.assertFalse(self.budget.quick_month_ids)
        self.assertEqual(self.budget.quick_annual_amount, 0)

    def test_specific_months_only(self):
        months = self.env['expense.budget.comparison.month'].search([
            ('number', 'in', [1, 3, 5]),
        ])
        lines = self._add(self.account2, 1200, months=months)
        self.assertEqual(len(lines), 3)
        self.assertEqual({int(item.month) for item in lines}, {1, 3, 5})
        self.assertTrue(all(item.planned_amount == 400 for item in lines))

    def test_no_month_selected_does_not_duplicate_existing(self):
        self._add(self.account, 1200)
        with self.assertRaises(UserError):
            with self.env.cr.savepoint():
                self._add(self.account, 1200)
        self.assertEqual(len(self.budget.line_ids.filtered(
            lambda line: line.account_id == self.account)), 12)

    def test_year_selector_does_not_change_year_storage_type(self):
        self.assertEqual(self.budget.year_selector, '2096')
        self.assertIsInstance(self.budget.year, int)
        self.budget.year_selector = '2097'
        self.assertEqual(self.budget.year, 2097)
        self.assertEqual(self.budget.year_selector, '2097')
        self.assertIn((str(date.today().year), str(date.today().year)),
                      self.env['expense.budget']._budget_year_choices())
