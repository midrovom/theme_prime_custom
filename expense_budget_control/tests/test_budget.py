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

    def test_annual_pdf_grouped_by_category_account_and_month(self):
        self.category.write({'name': 'Servicios básicos'})
        water = self.env['expense.budget.account'].create({
            'code': '6001-TEST', 'name': 'Agua', 'category_id': self.category.id,
            'company_id': self.company.id,
        })
        self.account.write({'name': 'Luz'})
        january_light = self.env['expense.budget.line'].create({
            'budget_id': self.budget.id, 'account_id': self.account.id,
            'month': '1', 'planned_amount': 100,
        })
        self.env['expense.budget.line'].create({
            'budget_id': self.budget.id, 'account_id': water.id,
            'month': '1', 'planned_amount': 200,
        })
        self.env['expense.budget.expense'].create({
            'company_id': self.company.id, 'account_id': self.account.id,
            'date': '2026-01-10', 'description': 'Electricidad', 'amount': 25,
        })
        self.env['expense.budget.expense'].create({
            'company_id': self.company.id, 'account_id': water.id,
            'date': '2026-01-12', 'description': 'Agua potable', 'amount': 50,
        })

        report = self.env['report.expense_budget_control.report_annual_budget_document']
        values = report._get_report_values([self.budget.id])
        self.assertEqual(len(values['reports']), 1)
        result = values['reports'][0]
        self.assertEqual(len(result['quarters']), 4)
        self.assertEqual(len(result['months']), 12)
        self.assertEqual(result['months'][11]['name'], 'Diciembre')
        self.assertEqual(result['quarters'][0]['months'][0]['name'], 'Enero')
        self.assertEqual(len(result['categories']), 1)
        category = result['categories'][0]
        self.assertEqual(category['category'].name, 'Servicios básicos')
        self.assertEqual({a['account'].name for a in category['accounts']}, {'Luz', 'Agua'})
        self.assertEqual(category['months']['1']['planned'], 300)
        self.assertEqual(category['months']['1']['actual'], 75)
        self.assertEqual(category['months']['1']['execution'], 25)
        self.assertEqual(result['totals']['1']['execution'], 25)
        self.assertEqual(category['annual']['planned'], 300)
        self.assertEqual(category['annual']['actual'], 75)
        self.assertEqual(category['annual']['execution'], 25)
        self.assertEqual(result['annual_total']['execution'], 25)
        self.assertEqual(january_light.execution_percentage, 25)
        self.assertFalse(result['totals']['2']['has_line'])

        action = self.budget.action_print_annual_pdf()
        self.assertEqual(action['type'], 'ir.actions.report')
        self.assertEqual(action['report_name'],
                         'expense_budget_control.report_annual_budget_document')

    def test_annual_report_uses_weighted_total_for_percentage(self):
        self.env['expense.budget.line'].create({
            'budget_id': self.budget.id, 'account_id': self.account.id,
            'month': '1', 'planned_amount': 100,
        })
        self.env['expense.budget.line'].create({
            'budget_id': self.budget.id, 'account_id': self.account.id,
            'month': '2', 'planned_amount': 300,
        })
        self.env['expense.budget.expense'].create({
            'company_id': self.company.id, 'account_id': self.account.id,
            'date': '2026-01-07', 'description': 'Gasto 1', 'amount': 100,
        })
        self.env['expense.budget.expense'].create({
            'company_id': self.company.id, 'account_id': self.account.id,
            'date': '2026-02-07', 'description': 'Gasto 2', 'amount': 60,
        })
        report = self.env['report.expense_budget_control.report_annual_budget_document']
        result = report._get_report_values([self.budget.id])['reports'][0]
        self.assertEqual(result['totals']['1']['execution'], 100)
        self.assertEqual(result['totals']['2']['execution'], 20)
        self.assertEqual(result['annual_total']['execution'], 40)
        self.assertEqual(result['categories'][0]['annual']['execution'], 40)
        self.assertEqual(result['categories'][0]['accounts'][0]['annual']['execution'], 40)
