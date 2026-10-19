# -*- coding: utf-8 -*-
"""Regresiones v1.4.66: subcentros seleccionables y filtro por periodo ERP."""
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestSubcentroERP1466(TransactionCase):
    def setUp(self):
        super().setUp()
        self.company = self.env.company
        self.center = self.env['expense.budget.cost.center'].create({
            'company_id': self.company.id, 'code': 'ANTEPARA66', 'name': 'Bodega',
        })
        self.account = self.env['expense.budget.account'].create({
            'company_id': self.company.id, 'code': '601010102002-66', 'name': 'Gasto',
        })
        self.sync = self.env['expense.budget.inventory.sync']

    def test_subcenter_codes_arrive_from_all_years_and_can_be_selected(self):
        rows = [
            {'Codigo': self.account.code, 'Valor': '45.26',
             'Fecha': 'abr  7 2026 12:00:00:000', 'Centro': 'ANTEPARA66   ',
             'Subcentro': 'GDE     '},
            {'Codigo': self.account.code, 'Valor': '50.00',
             'Fecha': 'may 25 2020 12:00:00:000', 'Centro': 'ANTEPARA66',
             'Subcentro': 'ADM     '},
        ]
        result = self.sync._sync_subcenters(self.company, rows)
        self.assertEqual(result['created'], 2)
        self.assertEqual(self.sync._sync_subcenters(self.company, rows)['unchanged'], 2)
        sub = self.env['expense.budget.subcenter'].search([
            ('company_id', '=', self.company.id),
            ('center_id', '=', self.center.id), ('code', '=', 'GDE'),
        ], limit=1)
        self.assertTrue(sub)
        budget = self.env['expense.budget'].with_context(
            skip_expense_budget_consumption_on_save=True).create({
                'company_id': self.company.id, 'name': 'Prueba ERP v1466', 'year': 2026,
            })
        line = self.env['expense.budget.line'].with_context(
            skip_expense_budget_consumption_on_save=True).create({
                'budget_id': budget.id, 'account_id': self.account.id,
                'cost_center_id': self.center.id, 'subcenter_id': sub.id,
                'month': '4', 'planned_amount': 100.0,
            })
        self.assertEqual(line.subcenter_code, 'GDE')
        self.assertEqual(line.subcenter_id, sub)
        self.assertEqual(len(self.sync._rows_for_saved_lines(rows, line)), 1)
        self.assertEqual(self.sync._rows_for_saved_lines(rows, line)[0]['Valor'], '45.26')

    def test_rubro_edition_from_field_remains_available(self):
        category = self.env['expense.budget.category'].create({
            'company_id': self.company.id, 'name': 'Nuevo rubro 66',
        })
        category.write({'account_selection_ids': [(6, 0, [self.account.id])]})
        self.assertEqual(self.account.category_id, category)
