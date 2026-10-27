# -*- coding: utf-8 -*-
"""1.4.74: Consumido mensual sin subcentro; PDF anual con centro de costo."""
from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import ValidationError


@tagged('post_install', '-at_install')
class TestConsumoSinSubcentro1474(TransactionCase):
    def test_mismo_codigo_centro_mes_agrega_todos_los_subcentros(self):
        company = self.env.company
        Account = self.env['expense.budget.account']
        Center = self.env['expense.budget.cost.center']
        AccountLine = self.env['expense.budget.line'].with_context(
            skip_expense_budget_consumption_on_save=True,
        )
        Expense = self.env['expense.budget.expense']
        account = Account.create({
            'company_id': company.id, 'code': '1474-601010102002',
            'name': 'Energía eléctrica',
        })
        center = Center.create({
            'company_id': company.id, 'code': '1474-QUITO', 'name': 'Quito',
        })
        category = self.env['expense.budget.category'].create({
            'company_id': company.id, 'name': 'Servicios 1474',
        })
        account.write({'category_id': category.id})
        budget = self.env['expense.budget'].with_context(
            skip_expense_budget_consumption_on_save=True,
        ).create({'company_id': company.id, 'year': 2026, 'name': 'Consumo 1474', 'category_id': category.id})
        line = AccountLine.create({
            'budget_id': budget.id, 'account_id': account.id,
            'cost_center_id': center.id, 'month': '1', 'planned_amount': 500,
        })
        def move(sub, date, amount, center_record=None):
            return Expense.create({
                'company_id': company.id, 'account_id': account.id,
                'cost_center_id': (center_record or center).id,
                'subcenter_code': sub, 'date': date, 'amount': amount,
                'description': 'Prueba 1474',
            })
        a = move('GND', '2026-01-03', 80)
        b = move('GDE', '2026-01-25', 41.72)
        move('GND', '2026-02-01', 900)
        move('GND', '2025-01-03', 800)
        self.assertEqual(a.budget_line_id, line)
        self.assertEqual(b.budget_line_id, line)
        self.assertAlmostEqual(line.actual_amount, 121.72)
        self.assertAlmostEqual(line.variance_amount, 378.28)
        rows = [
            {'Codigo': account.code, 'Centro': center.code, 'Subcentro': sub,
             'Fecha': date, 'Valor': str(amount)}
            for sub, date, amount in [
                ('GND', 'ene  3 2026 12:00:00:000', 80),
                ('GDE', 'ene 25 2026 12:00:00:000', 41.72),
                ('GND', 'feb  1 2026 12:00:00:000', 900),
                ('GND', 'ene  3 2025 12:00:00:000', 800),
            ]
        ]
        imported = self.env['expense.budget.inventory.sync']._rows_for_saved_lines(rows, line)
        self.assertEqual(len(imported), 2)
        with self.assertRaises(ValidationError):
            with self.env.cr.savepoint():
                AccountLine.create({
                    'budget_id': budget.id, 'account_id': account.id,
                    'cost_center_id': center.id, 'subcenter_code': 'OTRO',
                    'month': '1', 'planned_amount': 5,
                })
        report = self.env['report.expense_budget_control.report_annual_budget_document']
        data = report._prepare_budget(budget)
        self.assertEqual(data['categories'][0]['accounts'][0]['cost_center'], center)
        self.assertAlmostEqual(data['annual_total']['actual'], 121.72)
