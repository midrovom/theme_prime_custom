# -*- coding: utf-8 -*-
"""Consumo por MES de ERP, sin arrastrar movimientos de otros períodos."""
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestMonthlyConsumption1473(TransactionCase):
    def setUp(self):
        super().setUp()
        company = self.env.company
        self.company = company
        Account = self.env['expense.budget.account']
        Center = self.env['expense.budget.cost.center']
        self.water = Account.create({
            'company_id': company.id, 'code': '601010102001-TEST1473', 'name': 'Agua',
        })
        self.other_account = Account.create({
            'company_id': company.id, 'code': '601010101002-TEST1473', 'name': 'Otra cuenta',
        })
        self.quito = Center.create({
            'company_id': company.id, 'code': 'QUITO-TEST1473', 'name': 'Quito',
        })
        self.other_center = Center.create({
            'company_id': company.id, 'code': 'COSTA-TEST1473', 'name': 'Costa',
        })
        self.budget = self.env['expense.budget'].with_context(
            skip_expense_budget_consumption_on_save=True,
        ).create({'company_id': company.id, 'year': 2026, 'name': 'Presupuesto mensual 1473'})
        self.Line = self.env['expense.budget.line'].with_context(
            skip_expense_budget_consumption_on_save=True,
        )
        self.Expense = self.env['expense.budget.expense']

    def _move(self, account, center, subcenter, when, amount):
        return self.Expense.create({
            'company_id': self.company.id, 'account_id': account.id,
            'cost_center_id': center.id, 'subcenter_code': subcenter,
            'date': when, 'amount': amount, 'description': 'Consumo mensual de prueba',
        })

    def test_filtra_cuenta_centro_mes_y_anio_sin_subcentro(self):
        january = self.Line.create({
            'budget_id': self.budget.id, 'account_id': self.water.id,
            'cost_center_id': self.quito.id, 'subcenter_code': 'GND',
            'month': '1', 'planned_amount': 500,
        })
        self._move(self.water, self.quito, 'GND', '2026-01-02', 80)
        self._move(self.water, self.quito, 'GND', '2026-01-25', 41.72)
        self._move(self.water, self.quito, 'GND', '2026-02-02', 999)
        self._move(self.water, self.quito, 'GND', '2025-01-02', 900)
        self._move(self.water, self.quito, 'GDE', '2026-01-02', 700)
        self._move(self.water, self.other_center, 'GND', '2026-01-02', 600)
        self._move(self.other_account, self.quito, 'GND', '2026-01-02', 500)
        self.assertEqual(january.erp_matching_moves, 3)
        self.assertAlmostEqual(january.actual_amount, 821.72)
        self.assertAlmostEqual(january.variance_amount, -321.72)

    def test_api_historica_se_filtra_por_mes_sin_dia_exacto(self):
        january = self.Line.create({
            'budget_id': self.budget.id, 'account_id': self.water.id,
            'cost_center_id': self.quito.id, 'subcenter_code': 'GND',
            'month': '1', 'planned_amount': 500,
        })
        rows = [
            {'Codigo': self.water.code, 'Centro': self.quito.code,
             'Subcentro': 'GND', 'Fecha': when, 'Valor': str(amount)}
            for when, amount in [
                ('ene  5 2026 12:00:00:000', 100),
                ('ene 25 2026 12:00:00:000', 21.72),
                ('feb  5 2026 12:00:00:000', 999),
                ('ene  5 2025 12:00:00:000', 500),
            ]
        ]
        selected = self.env['expense.budget.inventory.sync']._rows_for_saved_lines(rows, january)
        self.assertEqual(len(selected), 2)
        self.assertAlmostEqual(sum(float(row['Valor']) for row in selected), 121.72)

    def test_fecha_antigua_oculta_no_restringe_mes(self):
        old = self.Line.create({
            'budget_id': self.budget.id, 'account_id': self.water.id,
            'cost_center_id': self.quito.id, 'subcenter_code': 'GND',
            'consumption_date': '2026-01-25', 'planned_amount': 500,
        })
        self._move(self.water, self.quito, 'GND', '2026-01-05', 12)
        self._move(self.water, self.quito, 'GND', '2026-01-25', 23)
        self.assertAlmostEqual(old.actual_amount, 35)
        old.write({'month': '2'})
        self.assertFalse(old.consumption_date)
        self.assertAlmostEqual(old.actual_amount, 0)
