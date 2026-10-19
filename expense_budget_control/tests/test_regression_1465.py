# -*- coding: utf-8 -*-
"""Regresión v1.4.65: fecha exacta, subcentro proveniente del ERP."""
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestBudgetSubcentroAutomatico1465(TransactionCase):
    def setUp(self):
        super().setUp()
        self.company = self.env.company
        self.sync = self.env['expense.budget.inventory.sync']
        self.account = self.env['expense.budget.account'].create({
            'company_id': self.company.id, 'code': '601010101001-AUTO65',
            'name': 'Sueldos y Salarios',
        })
        self.center = self.env['expense.budget.cost.center'].create({
            'company_id': self.company.id, 'code': 'ADM-AUTO65',
            'name': 'Administración',
        })
        self.other_center = self.env['expense.budget.cost.center'].create({
            'company_id': self.company.id, 'code': 'MAT-AUTO65',
            'name': 'MAT',
        })
        self.budget = self.env['expense.budget'].with_context(
            skip_expense_budget_consumption_on_save=True,
        ).create({'company_id': self.company.id, 'name': 'Prueba mes ERP', 'year': 2026})
        self.Line = self.env['expense.budget.line'].with_context(
            skip_expense_budget_consumption_on_save=True,
        )
        self.Expense = self.env['expense.budget.expense']

    def test_abril_no_suma_marzo_mayo_ni_otros_anios_o_centros(self):
        april = self.Line.create({
            'budget_id': self.budget.id, 'account_id': self.account.id,
            'cost_center_id': self.center.id, 'month': '4',
            'planned_amount': 10000,
        })
        may = self.Line.create({
            'budget_id': self.budget.id, 'account_id': self.account.id,
            'cost_center_id': self.center.id, 'month': '5',
            'planned_amount': 10000,
        })
        rows = [
            {'Codigo': self.account.code, 'Centro': 'ADM-AUTO65   ',
             'Subcentro': 'GDE   ', 'Fecha': 'abr 25 2026 12:00:00:000', 'Valor': '2304.26'},
            {'Codigo': self.account.code, 'Centro': 'ADM-AUTO65',
             'Subcentro': 'VTA', 'Fecha': 'abr 26 2026 12:00:00:000', 'Valor': '50.00'},
            {'Codigo': self.account.code, 'Centro': 'ADM-AUTO65',
             'Subcentro': 'GDE', 'Fecha': 'mar 25 2026 12:00:00:000', 'Valor': '990'},
            {'Codigo': self.account.code, 'Centro': 'ADM-AUTO65',
             'Subcentro': 'GDE', 'Fecha': 'may 25 2026 12:00:00:000', 'Valor': '100'},
            {'Codigo': self.account.code, 'Centro': 'ADM-AUTO65',
             'Subcentro': 'GDE', 'Fecha': 'abr 25 2020 12:00:00:000', 'Valor': '900'},
            {'Codigo': self.account.code, 'Centro': 'MAT-AUTO65',
             'Subcentro': 'GDE', 'Fecha': 'abr 25 2026 12:00:00:000', 'Valor': '500'},
        ]
        # El filtro no obliga a escribir un subcentro en la proyección.
        selected = self.sync._rows_for_saved_lines(rows, april)
        self.assertEqual(len(selected), 2)
        self.assertEqual(sum(float(r['Valor']) for r in selected), 2354.26)
        self.assertFalse(april.subcenter_code)
        self.Expense.create({
            'company_id': self.company.id, 'account_id': self.account.id,
            'cost_center_id': self.center.id, 'subcenter_code': 'GDE',
            'date': '2026-04-25', 'amount': 2304.26, 'description': 'API abr GDE',
        })
        self.Expense.create({
            'company_id': self.company.id, 'account_id': self.account.id,
            'cost_center_id': self.center.id, 'subcenter_code': 'VTA',
            'date': '2026-04-26', 'amount': 50, 'description': 'API abr VTA',
        })
        self.Expense.create({
            'company_id': self.company.id, 'account_id': self.account.id,
            'cost_center_id': self.center.id, 'subcenter_code': 'GDE',
            'date': '2026-05-25', 'amount': 100, 'description': 'API may',
        })
        self.assertAlmostEqual(april.actual_amount, 2354.26)
        self.assertEqual(april.erp_subcenter_codes, 'GDE, VTA')
        self.assertAlmostEqual(may.actual_amount, 100)
        self.assertEqual(may.erp_subcenter_codes, 'GDE')

    def test_reconciliar_gasto_anteriormente_vinculado_al_mes_equivocado(self):
        april = self.Line.create({
            'budget_id': self.budget.id, 'account_id': self.account.id,
            'cost_center_id': self.center.id, 'month': '4', 'planned_amount': 100,
        })
        may = self.Line.create({
            'budget_id': self.budget.id, 'account_id': self.account.id,
            'cost_center_id': self.center.id, 'month': '5', 'planned_amount': 100,
        })
        expense = self.Expense.create({
            'company_id': self.company.id, 'account_id': self.account.id,
            'cost_center_id': self.center.id, 'subcenter_code': 'GDE',
            'date': '2026-05-25', 'amount': 161.82, 'description': 'Gasto de mayo',
        })
        # Una escritura ORM con mes incorrecto se bloquea por consistencia.
        # Simular datos enlazados por una versión antigua mediante SQL.
        self.env.cr.execute('UPDATE expense_budget_expense SET budget_line_id = %s WHERE id = %s',
                            (april.id, expense.id))
        self.env.invalidate_all()
        # Aunque el vínculo estuviese corrupto, el Consumido comprueba la fecha.
        self.assertAlmostEqual(april.actual_amount, 0.0)
        self.assertEqual(self.sync._reconcile_saved_line_periods(april), 1)
        self.assertEqual(expense.budget_line_id, may)
        self.assertAlmostEqual(april.actual_amount, 0.0)
        self.assertAlmostEqual(may.actual_amount, 161.82)
