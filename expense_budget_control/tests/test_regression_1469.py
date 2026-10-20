# -*- coding: utf-8 -*-
"""Regresión histórica 1.4.69, adaptada al retorno a períodos mensuales."""
from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestBudgetMonthlyAfterDate1469(TransactionCase):
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
                  'name': 'Pruebas consumos mensuales'})
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

    def test_noviembre_suma_dias_y_excluye_otro_mes_y_anio(self):
        november = self._line(month='11', subcenter_code='GDE')
        self._expense('2023-11-25', 2304.26)
        self._expense('2023-11-26', 50)
        self._expense('2023-10-25', 100)
        self._expense('2022-11-25', 200)
        self._expense('2023-11-25', 300, sub='VTA')
        self.assertAlmostEqual(november.actual_amount, 2654.26)
        self.assertEqual(self.Expense._find_budget_line(
            self.company.id, self.account.id, '2023-11-26', self.center.id, 'GDE'), november)
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
        chosen = self.sync._rows_for_saved_lines(rows, november)
        self.assertEqual(len(chosen), 2)
        self.assertAlmostEqual(sum(float(item['Valor']) for item in chosen), 2354.26)

    def test_fecha_heredada_no_limita_el_mes(self):
        # Registros creados con el antiguo selector diario también deben
        # calcular el mes completo, aunque la fecha permanezca en BBDD.
        old = self._line(consumption_date='2023-11-25', subcenter_code='GDE')
        self._expense('2023-11-20', 25)
        self._expense('2023-11-25', 50)
        self.assertAlmostEqual(old.actual_amount, 75)
        self.assertEqual(old.month, '11')

    def test_fecha_heredada_fuera_anio_rechazada(self):
        with self.assertRaises(ValidationError):
            with self.env.cr.savepoint():
                self._line(consumption_date='2024-11-25')

    def test_editar_mes_reubica_gastos_locales(self):
        original = self._line(month='11')
        expense_nov = self._expense('2023-11-25', 80)
        expense_oct = self._expense('2023-10-26', 15)
        self.assertAlmostEqual(original.actual_amount, 80)
        original.write({'month': '10'})
        self.assertFalse(original.consumption_date)
        self.assertFalse(expense_nov.budget_line_id)
        self.assertEqual(expense_oct.budget_line_id, original)
        self.assertAlmostEqual(original.actual_amount, 15)
