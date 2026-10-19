# -*- coding: utf-8 -*-
"""Pruebas ERP en base Odoo de pruebas (no contactan endpoints remotos)."""
from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import ValidationError

from odoo.addons.expense_budget_control.models.inventory_api import parse_erp_date


@tagged('post_install', '-at_install')
class TestBudgetERPIntegration(TransactionCase):

    def setUp(self):
        super().setUp()
        self.company = self.env.company
        self.sync = self.env['expense.budget.inventory.sync']
        self.account_model = self.env['expense.budget.account']
        self.center_model = self.env['expense.budget.cost.center']

    def test_spanish_dates(self):
        self.assertEqual(str(parse_erp_date('abr 25 2026 12:00:00:000')), '2026-04-25')
        self.assertEqual(str(parse_erp_date('ago 25 2026 12:00:00:000')), '2026-08-25')
        self.assertEqual(str(parse_erp_date('mar 25 2020 12:00:00:000')), '2020-03-25')

    def test_catalogs_update_by_company_and_code(self):
        row = [{'Codigo': '601010101001 ', 'Nombre': ' Sueldos y Salarios '}]
        one = self.sync._sync_accounts(self.company, row)
        self.assertEqual(one['created'], 1)
        two = self.sync._sync_accounts(self.company, row)
        self.assertEqual(two['unchanged'], 1)
        three = self.sync._sync_accounts(self.company, [
            {'Codigo': '601010101001', 'Nombre': 'Sueldos modificados'},
        ])
        self.assertEqual(three['updated'], 1)
        self.assertEqual(self.account_model.search_count([
            ('company_id', '=', self.company.id), ('code', '=', '601010101001'),
        ]), 1)
        c = self.sync._sync_centers(self.company, [
            {'Codigo': 'MAT       ', 'Nombre': 'MAT- ALB - NEXUS              '},
        ])
        self.assertEqual(c['created'], 1)
        self.assertEqual(self.center_model.search([
            ('company_id', '=', self.company.id), ('code', '=', 'MAT'),
        ], limit=1).name, 'MAT- ALB - NEXUS')

    def test_consumption_normalization(self):
        code, center, subcenter, when, value, external_id = self.sync._normalize_consumption({
            'Codigo': '601010101001', 'Valor': '2431.03',
            'Fecha': 'mar 25 2020 12:00:00:000',
            'Centro': 'ALM       ', 'Subcentro': 'GDE       ',
        })
        self.assertEqual((code, center, subcenter), ('601010101001', 'ALM', 'GDE'))
        self.assertEqual(str(when), '2020-03-25')
        self.assertEqual(value, 2431.03)
        self.assertFalse(external_id)

    def test_nested_payload_and_optional_endpoint_query(self):
        from types import SimpleNamespace
        rows = self.sync._rows({'data': {'items': [
            {'Codigo': '601010101002', 'Nombre': 'Decimo Tercer Sueldo'},
        ]}})
        self.assertEqual(len(rows), 1)
        self.assertTrue(self.sync._matches_endpoint(SimpleNamespace(
            end_point='https://example.invalid/inventory_odoo/consulta_odoo/getconsumosgastos/2?x=1',
        ), 'consumptions'))

    def test_subcenter_year_month_center_and_consumed(self):
        """La proyección 2022 ADM/GDE recibe 161.82; otros años/centros no."""
        account = self.account_model.create({
            'company_id': self.company.id, 'code': '601010101002',
            'name': 'Decimo Tercer Sueldo',
        })
        center = self.center_model.create({
            'company_id': self.company.id, 'code': 'ADM', 'name': 'Administración',
        })
        budget_2022 = self.env['expense.budget'].create({
            'company_id': self.company.id, 'name': 'Personal 2022', 'year': 2022,
        })
        budget_2026 = self.env['expense.budget'].create({
            'company_id': self.company.id, 'name': 'Personal 2026', 'year': 2026,
        })
        line_model = self.env['expense.budget.line']
        line_2022 = line_model.create({
            'budget_id': budget_2022.id, 'account_id': account.id,
            'cost_center_id': center.id, 'subcenter_code': 'GDE',
            'month': '7', 'planned_amount': 200,
        })
        line_2026 = line_model.create({
            'budget_id': budget_2026.id, 'account_id': account.id,
            'cost_center_id': center.id, 'subcenter_code': 'GDE',
            'month': '7', 'planned_amount': 300,
        })
        expense_model = self.env['expense.budget.expense']
        expense = expense_model.create({
            'company_id': self.company.id, 'account_id': account.id,
            'cost_center_id': center.id, 'subcenter_code': 'GDE',
            'date': '2022-07-25', 'amount': 161.82,
            'description': 'Consumo API de prueba',
        })
        self.assertEqual(expense.budget_line_id, line_2022)
        self.assertAlmostEqual(line_2022.actual_amount, 161.82)
        self.assertAlmostEqual(line_2026.actual_amount, 0.0)
        self.assertFalse(expense_model._find_budget_line(
            self.company.id, account.id, '2022-07-25', False, 'GDE'))

    def test_subcenter_exact_precedes_generic_and_unmatched_stays_unlinked(self):
        account = self.account_model.create({
            'company_id': self.company.id, 'code': '601010101099',
            'name': 'Servicios para subcentros',
        })
        center = self.center_model.create({
            'company_id': self.company.id, 'code': 'ADM-TEST-SUB', 'name': 'Administración',
        })
        budget = self.env['expense.budget'].create({
            'company_id': self.company.id, 'name': 'Prueba subcentros', 'year': 2091,
        })
        Line = self.env['expense.budget.line']
        generic = Line.create({
            'budget_id': budget.id, 'account_id': account.id,
            'cost_center_id': center.id, 'month': '6', 'planned_amount': 200,
        })
        Expense = self.env['expense.budget.expense']
        first = Expense.create({
            'company_id': self.company.id, 'account_id': account.id,
            'cost_center_id': center.id, 'subcenter_code': 'GDE',
            'date': '2091-06-15', 'amount': 40, 'description': 'Antes de especificar',
        })
        self.assertEqual(first.budget_line_id, generic)
        specific = Line.create({
            'budget_id': budget.id, 'account_id': account.id,
            'cost_center_id': center.id, 'subcenter_code': 'GDE',
            'month': '6', 'planned_amount': 120,
        })
        self.assertEqual(first.budget_line_id, specific)
        second = Expense.create({
            'company_id': self.company.id, 'account_id': account.id,
            'cost_center_id': center.id, 'subcenter_code': 'OTRO',
            'date': '2091-06-17', 'amount': 30, 'description': 'Otro subcentro',
        })
        self.assertEqual(second.budget_line_id, generic)
        self.assertAlmostEqual(specific.actual_amount, 40)
        self.assertAlmostEqual(generic.actual_amount, 30)
