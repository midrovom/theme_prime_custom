# -*- coding: utf-8 -*-
"""Regresiones v1.4.64: catálogos idempotentes y edición de rubros."""
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestBudgetCatalogAndCategories1464(TransactionCase):
    def setUp(self):
        super().setUp()
        self.company = self.env.company
        self.sync = self.env['expense.budget.inventory.sync']
        self.Account = self.env['expense.budget.account']
        self.Center = self.env['expense.budget.cost.center']

    def test_reimport_existing_catalogs_without_unique_error(self):
        # Caso reportado: la API recibe códigos que ya existen en la empresa.
        account = self.Account.create({
            'company_id': self.company.id, 'code': '601010101001',
            'name': 'Nombre anterior',
        })
        center = self.Center.create({
            'company_id': self.company.id, 'code': 'MAT',
            'name': 'Centro anterior',
        })
        accounts = [{'Codigo': '601010101001 ', 'Nombre': 'Sueldos y Salarios'}]
        centers = [{'Codigo': 'MAT        ', 'Nombre': 'MAT- ALB - NEXUS'}]
        self.assertEqual(self.sync._sync_accounts(self.company, accounts)['updated'], 1)
        self.assertEqual(self.sync._sync_centers(self.company, centers)['updated'], 1)
        self.assertEqual(self.sync._sync_accounts(self.company, accounts)['unchanged'], 1)
        self.assertEqual(self.sync._sync_centers(self.company, centers)['unchanged'], 1)
        self.assertEqual(account.name, 'Sueldos y Salarios')
        self.assertEqual(center.name, 'MAT- ALB - NEXUS')
        self.assertEqual(self.Account.with_context(active_test=False).search_count([
            ('company_id', '=', self.company.id), ('code', '=', '601010101001'),
        ]), 1)
        self.assertEqual(self.Center.with_context(active_test=False).search_count([
            ('company_id', '=', self.company.id), ('code', '=', 'MAT'),
        ]), 1)

    def test_registrar_create_category_first_edit_accounts_later(self):
        group = self.env.ref('expense_budget_control.group_expense_budget_registrar')
        base_group = self.env.ref('base.group_user')
        registrar = self.env['res.users'].create({
            'name': 'Registrador pruebas rubros',
            'login': 'registrador_rubros_1464@example.invalid',
            'company_id': self.company.id,
            'company_ids': [(6, 0, [self.company.id])],
            'groups_id': [(6, 0, [base_group.id, group.id])],
        })
        account = self.Account.create({
            'company_id': self.company.id, 'code': 'CUENTA-EDITAR-1464',
            'name': 'Cuenta configurable',
        })
        category_model = self.env['expense.budget.category'].with_user(registrar)
        # El rubro solo necesita nombre y empresa, NO línea ni cuenta ni mes.
        category = category_model.create({
            'company_id': self.company.id, 'name': 'Rubro nuevo',
        })
        self.assertTrue(category.code)
        self.assertFalse(category.account_ids)
        # Abrir la misma ficha y asignar la cuenta en una edición posterior.
        category.write({'account_selection_ids': [(6, 0, [account.id])]})
        self.assertEqual(account.category_id, category)
        # Sin proyecciones o gastos previos, se puede quitar posteriormente.
        category.write({'account_selection_ids': [(6, 0, [])]})
        self.assertFalse(account.category_id)
