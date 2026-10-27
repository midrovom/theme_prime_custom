# -*- coding: utf-8 -*-
"""Regresión de la nueva dimensión centro de costo y compatibilidad heredada."""
from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import ValidationError
from psycopg2 import IntegrityError


@tagged('post_install', '-at_install')
class TestExpenseBudgetCostCenter(TransactionCase):
    def setUp(self):
        super().setUp()
        self.company = self.env.company
        self.account = self.env['expense.budget.account'].create({
            'code': 'CC-ACC-459', 'name': 'Luz', 'company_id': self.company.id,
        })
        category = self.env['expense.budget.category'].create({
            'company_id': self.company.id, 'name': 'Servicios por centro',
        })
        self.account.write({'category_id': category.id})
        self.category = category
        self.center_a = self.env['expense.budget.cost.center'].create({
            'code': 'CC-ADM-459', 'name': 'Administración', 'company_id': self.company.id,
        })
        self.center_b = self.env['expense.budget.cost.center'].create({
            'code': 'CC-OPS-459', 'name': 'Operaciones', 'company_id': self.company.id,
        })
        self.budget = self.env['expense.budget'].create({
            'name': 'Presupuesto por centros', 'company_id': self.company.id, 'year': 2085, 'category_id': self.category.id,
        })

    def test_same_account_and_month_in_separate_centers(self):
        Line = self.env['expense.budget.line']
        first = Line.create({
            'budget_id': self.budget.id, 'account_id': self.account.id,
            'cost_center_id': self.center_a.id, 'month': '1', 'planned_amount': 100,
        })
        second = Line.create({
            'budget_id': self.budget.id, 'account_id': self.account.id,
            'cost_center_id': self.center_b.id, 'month': '1', 'planned_amount': 200,
        })
        self.assertNotEqual(first, second)
        self.assertEqual(self.budget.planned_amount, 300)
        with self.assertRaises((ValidationError, IntegrityError)):
            with self.env.cr.savepoint():
                Line.create({
                    'budget_id': self.budget.id, 'account_id': self.account.id,
                    'cost_center_id': self.center_a.id, 'month': '1', 'planned_amount': 400,
                })

    def test_expense_is_matched_to_correct_center(self):
        Line = self.env['expense.budget.line']
        for center in (self.center_a, self.center_b):
            Line.create({
                'budget_id': self.budget.id, 'account_id': self.account.id,
                'cost_center_id': center.id, 'month': '1', 'planned_amount': 500,
            })
        expense = self.env['expense.budget.expense'].create({
            'company_id': self.company.id, 'account_id': self.account.id,
            'cost_center_id': self.center_b.id, 'date': '2085-01-20',
            'amount': 75, 'description': 'Luz de operaciones',
        })
        self.assertEqual(expense.budget_line_id.cost_center_id, self.center_b)
        self.assertAlmostEqual(expense.budget_line_id.actual_amount, 75)
        center_a_line = Line.search([('cost_center_id', '=', self.center_a.id),
                                     ('budget_id', '=', self.budget.id)], limit=1)
        self.assertAlmostEqual(center_a_line.actual_amount, 0)

    def test_existing_line_without_center_still_supported(self):
        line = self.env['expense.budget.line'].create({
            'budget_id': self.budget.id, 'account_id': self.account.id,
            'month': '2', 'planned_amount': 60,
        })
        self.assertFalse(line.cost_center_id)
        expense = self.env['expense.budget.expense'].create({
            'company_id': self.company.id, 'account_id': self.account.id,
            'date': '2085-02-20', 'amount': 10, 'description': 'Gasto heredado',
        })
        self.assertEqual(expense.budget_line_id, line)

    def test_cost_center_catalog_structure(self):
        sync = self.env['expense.budget.cost.center.sync']
        rows = sync._extract_rows({'data': [
            {'company_id': self.company.name, 'code': 'CC01', 'name': 'Administración'},
            {'company_id': self.company.name, 'code': 'CC02', 'name': 'Operaciones'},
        ]})
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1]['code'], 'CC02')
