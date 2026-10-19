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
