# -*- coding: utf-8 -*-
"""Parser de fechas ERP, presupuesto vacío y diferencia entre meses."""
from datetime import date
from unittest.mock import patch

from odoo.tests.common import TransactionCase, tagged
from ..models.inventory_api import parse_erp_date


@tagged('post_install', '-at_install')
class TestBudgetDateAndEmptySave1470(TransactionCase):
    def setUp(self):
        super().setUp()
        self.company = self.env.company
        self.Account = self.env['expense.budget.account']
        self.Center = self.env['expense.budget.cost.center']
        self.Budget = self.env['expense.budget']
        self.Sync = self.env['expense.budget.inventory.sync']
        self.Expense = self.env['expense.budget.expense']

    def test_parser_ocho_octubre_con_espacios(self):
        self.assertEqual(parse_erp_date('oct  8 2026 12:00:00:000'), date(2026, 10, 8))

    def test_presupuesto_sin_lineas_no_consulta_erp(self):
        with patch.object(type(self.Sync), '_sync_saved_lines', side_effect=AssertionError(
            'Un presupuesto vacío no puede consultar consumos ERP')):
            budget = self.Budget.create({
                'name': 'Presupuesto vacío, prueba sin ERP',
                'year': 2096, 'company_id': self.company.id,
            })
            budget.write({'note': 'Edición de cabecera sin proyecciones'})
        self.assertFalse(budget.line_ids)

    def test_septiembre_no_suma_octubre_y_octubre_suma_todos_sus_dias(self):
        account = self.Account.create({
            'name': 'Agua', 'code': 'T1470-601010102001',
            'company_id': self.company.id,
        })
        center = self.Center.create({
            'name': 'Quito', 'code': 'T1470-QUITO',
            'company_id': self.company.id,
        })
        budget = self.Budget.with_context(
            skip_expense_budget_consumption_on_save=True,
        ).create({'name': 'Consumo octubre', 'year': 2026, 'company_id': self.company.id})
        Line = self.env['expense.budget.line'].with_context(
            skip_expense_budget_consumption_on_save=True,
        )
        line = Line.create({
            'budget_id': budget.id, 'account_id': account.id,
            'cost_center_id': center.id, 'subcenter_code': 'GND',
            'month': '9', 'planned_amount': 150,
        })
        self.Expense.create({
            'company_id': self.company.id, 'account_id': account.id,
            'cost_center_id': center.id, 'subcenter_code': 'GND',
            'date': '2026-10-08', 'amount': 121.72,
            'description': 'Movimiento de consumo octubre',
        })
        self.Expense.create({
            'company_id': self.company.id, 'account_id': account.id,
            'cost_center_id': center.id, 'subcenter_code': 'GND',
            'date': '2026-10-25', 'amount': 22,
            'description': 'Otro movimiento del mes',
        })
        self.assertAlmostEqual(line.actual_amount, 0)
        self.assertEqual(line.consultation_date_label, 'Mes completo: septiembre de 2026')
        line.write({'month': '10'})
        self.assertEqual(line.consultation_date_label, 'Mes completo: octubre de 2026')
        self.assertAlmostEqual(line.actual_amount, 143.72)
