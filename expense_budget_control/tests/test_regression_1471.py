# -*- coding: utf-8 -*-
"""No confundir la etiqueta de una cuenta con su código ERP real."""
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestBudgetERPMatching1471(TransactionCase):
    def test_account_code_is_authoritative(self):
        company = self.env.company
        Account = self.env['expense.budget.account']
        Center = self.env['expense.budget.cost.center']
        Budget = self.env['expense.budget']
        Line = self.env['expense.budget.line']
        Expense = self.env['expense.budget.expense']
        center = Center.create({'company_id': company.id,
                                'code': 'MATCH71-QUITO', 'name': 'Quito'})
        # Igual que el caso reportado: la etiqueta Agua NO es el código
        # 601010101002 que el ERP asigna a Décimo Tercer Sueldo.
        water = Account.create({'company_id': company.id,
                                'code': 'MATCH71-AGUA', 'name': 'Agua'})
        salary = Account.create({'company_id': company.id,
                                 'code': '601010101002-MATCH71',
                                 'name': 'Décimo Tercer Sueldo'})
        category = self.env['expense.budget.category'].create({
            'company_id': company.id, 'name': 'Rubro pruebas 1471',
        })
        (water | salary).write({'category_id': category.id})
        budget = Budget.with_context(skip_expense_budget_consumption_on_save=True).create({
            'company_id': company.id, 'year': 2026, 'name': 'Regresión ERP código de cuenta', 'category_id': category.id,
        })
        vals = {'budget_id': budget.id, 'cost_center_id': center.id,
                'month': '6', 'subcenter_code': 'GDE',
                'planned_amount': 1000}
        water_line = Line.with_context(skip_expense_budget_consumption_on_save=True).create({
            **vals, 'account_id': water.id,
        })
        salary_line = Line.with_context(skip_expense_budget_consumption_on_save=True).create({
            **vals, 'account_id': salary.id,
        })
        expense = Expense.create({
            'company_id': company.id, 'account_id': salary.id,
            'cost_center_id': center.id, 'subcenter_code': 'GDE',
            'date': '2026-06-25', 'amount': 210.88, 'description': 'Movimiento ERP',
        })
        self.assertEqual(expense.budget_line_id, salary_line)
        self.assertEqual(water_line.erp_account_code, 'MATCH71-AGUA')
        self.assertEqual(salary_line.erp_account_code, '601010101002-MATCH71')
        self.assertEqual(water_line.erp_matching_moves, 0)
        self.assertEqual(water_line.actual_amount, 0)
        self.assertEqual(salary_line.erp_matching_moves, 1)
        self.assertAlmostEqual(salary_line.actual_amount, 210.88)
