# -*- coding: utf-8 -*-
"""Fecha ERP exacta (día/mes/año) y compatibilidad de líneas mensuales."""
from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestBudgetDateExact1469(TransactionCase):
    def setUp(self):
        super().setUp()
        self.company = self.env.company
        self.account = self.env['expense.budget.account'].create({
            'company_id': self.company.id, 'code': 'DATE69-601010101001',
            'name': 'Sueldos y Salarios',
        })
        self.center = self.env['expense.budget.cost.center'].create({
            'company_id': self.company.id, 'code': 'DATE69-ADM', 'name': 'Centro de costo',
        })
        self.budget = self.env['expense.budget'].with_context(
            skip_expense_budget_consumption_on_save=True,
        ).create({'company_id': self.company.id, 'year': 2023,
                  'name': 'Pruebas consumos fechas exactas'})
        self.Line = self.env['expense.budget.line'].with_context(
            skip_expense_budget_consumption_on_save=True,
        )
        self.Expense = self.env['expense.budget.expense']
        self.sync = self.env['expense.budget.inventory.sync']

    def _line(self, **kwargs):
        vals = {'budget_id': self.budget.id, 'account_id': self.account.id,
                'cost_center_id': self.center.id, 'planned_amount': 10000}
        vals.update(kwargs)
        return self.Line.create(vals)

    def _expense(self, when, amount, sub='GDE'):
        return self.Expense.create({
            'company_id': self.company.id, 'account_id': self.account.id,
            'cost_center_id': self.center.id, 'subcenter_code': sub,
            'date': when, 'amount': amount, 'description': 'Consumo ERP test',
        })

    def test_25_noviembre_no_suma_otros_dias_ni_anios(self):
        nov25 = self._line(consumption_date='2023-11-25', subcenter_code='GDE')
        nov26 = self._line(consumption_date='2023-11-26', subcenter_code='GDE')
        self.assertEqual(nov25.month, '11')
        self.assertEqual(nov26.month, '11')
        self._expense('2023-11-25', 2304.26)
        self._expense('2023-11-26', 50)
        self._expense('2023-10-25', 100)
        self._expense('2022-11-25', 200)
        self._expense('2023-11-25', 300, sub='VTA')
        self.assertAlmostEqual(nov25.actual_amount, 2304.26)
        self.assertAlmostEqual(nov26.actual_amount, 50)
        self.assertEqual(self.Expense._find_budget_line(
            self.company.id, self.account.id, '2023-11-25', self.center.id, 'GDE'), nov25)
        rows = [
            {'Codigo': self.account.code, 'Centro': self.center.code,
             'Subcentro': 'GDE', 'Fecha': when, 'Valor': str(amount)}
            for when, amount in [
                ('nov 25 2023 12:00:00:000', 2304.26),
                ('nov 26 2023 12:00:00:000', 50),
                ('oct 25 2023 12:00:00:000', 100),
                ('nov 25 2022 12:00:00:000', 200),
            ]
        ]
        chosen = self.sync._rows_for_saved_lines(rows, nov25)
        self.assertEqual(len(chosen), 1)
        self.assertEqual(chosen[0]['Valor'], '2304.26')

    def test_linea_antigua_sin_fecha_sigue_sumando_mes(self):
        legacy = self._line(month='11')
        self._expense('2023-11-20', 25)
        self._expense('2023-11-25', 50)
        self.assertFalse(legacy.consumption_date)
        self.assertAlmostEqual(legacy.actual_amount, 75)

    def test_fecha_fuera_anio_rechazada(self):
        with self.assertRaises(ValidationError):
            with self.env.cr.savepoint():
                self._line(consumption_date='2024-11-25')

    def test_editar_fecha_reubica_gastos_locales(self):
        original = self._line(month='11')
        expense25 = self._expense('2023-11-25', 80)
        expense26 = self._expense('2023-11-26', 15)
        self.assertAlmostEqual(original.actual_amount, 95)
        original.write({'consumption_date': '2023-11-25'})
        self.assertEqual(original.month, '11')
        self.assertEqual(expense25.budget_line_id, original)
        self.assertFalse(expense26.budget_line_id)
        self.assertAlmostEqual(original.actual_amount, 80)
