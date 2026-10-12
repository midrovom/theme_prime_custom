# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import UserError


@tagged('post_install', '-at_install')
class TestExpenseBudget(TransactionCase):

    def setUp(self):
        super().setUp()
        self.company = self.env.company
        self.category = self.env['expense.budget.category'].create({
            'code': 'ADM-TEST', 'name': 'Administración', 'company_id': self.company.id,
        })
        self.account = self.env['expense.budget.account'].create({
            'code': '6000-TEST', 'name': 'Servicios', 'category_id': self.category.id,
            'company_id': self.company.id,
        })
        self.budget = self.env['expense.budget'].create({
            'name': 'Test presupuestario', 'year': 2026, 'company_id': self.company.id,
        })

    def test_planned_vs_actual(self):
        line = self.env['expense.budget.line'].create({
            'budget_id': self.budget.id, 'account_id': self.account.id,
            'month': '10', 'planned_amount': 1000,
        })
        movement = self.env['expense.budget.expense'].create({
            'company_id': self.company.id, 'account_id': self.account.id,
            'date': '2026-10-01', 'description': 'Licencias', 'amount': 250,
        })
        self.assertEqual(movement.budget_line_id, line)
        self.assertEqual(line.actual_amount, 250)
        self.assertEqual(line.variance_amount, 750)
        self.assertEqual(self.budget.actual_amount, 250)
        movement.write({'amount': 300})
        self.assertEqual(line.actual_amount, 300)
        movement.unlink()
        self.assertEqual(line.actual_amount, 0)

    def test_reconcile_expense_created_before_line(self):
        expense = self.env['expense.budget.expense'].create({
            'company_id': self.company.id, 'account_id': self.account.id,
            'date': '2026-02-17', 'description': 'Reparación', 'amount': 80,
        })
        self.assertFalse(expense.budget_line_id)
        line = self.env['expense.budget.line'].create({
            'budget_id': self.budget.id, 'account_id': self.account.id,
            'month': '2', 'planned_amount': 100,
        })
        self.assertEqual(expense.budget_line_id, line)
        self.assertEqual(line.actual_amount, 80)

    def test_idempotent_import_and_reversal(self):
        data = {'codigo_cuenta': '6000-TEST', 'fecha': '2026-10-12',
                'monto': '125,50', 'descripcion': 'Energía'}
        Expense = self.env['expense.budget.expense']
        self.assertEqual(Expense._upsert_external(self.company, data, 'excel', 'INV-101'), 'created')
        self.assertEqual(Expense._upsert_external(self.company, data, 'excel', 'INV-101'), 'unchanged')
        self.assertEqual(Expense.search_count([('source_key', '=', 'excel:INV-101')]), 1)
        data['monto'] = '-20'
        self.assertEqual(Expense._upsert_external(self.company, data, 'excel', 'INV-101'), 'updated')

    def test_budget_approval_locks_lines(self):
        line = self.env['expense.budget.line'].create({
            'budget_id': self.budget.id, 'account_id': self.account.id,
            'month': '1', 'planned_amount': 500,
        })
        self.budget.action_approve()
        with self.assertRaises(UserError):
            line.write({'planned_amount': 600})
