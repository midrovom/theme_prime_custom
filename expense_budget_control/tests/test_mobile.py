# -*- coding: utf-8 -*-
"""Mobile navigation should expose only existing role-authorized sections."""
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestExpenseBudgetMobileNavigation(TransactionCase):
    def _navigation_as(self, group):
        user = self.env['res.users'].create({
            'name': 'Mobile navigation tester ' + group,
            'login': 'mobile_' + group + '@example.invalid',
            'groups_id': [(6, 0, [
                self.env.ref('base.group_user').id,
                self.env.ref('expense_budget_control.' + group).id,
            ])],
        })
        return self.env['expense.budget.dashboard'].with_user(user).get_mobile_navigation()

    def test_registrar_only_budget_and_import(self):
        titles = {section['title'] for section in
                  self._navigation_as('group_expense_budget_registrar')}
        self.assertIn('Presupuestos', titles)
        self.assertIn('Importar Excel / CSV', titles)
        self.assertNotIn('Aprobación de presupuestos', titles)
        self.assertNotIn('Configuración API de gastos', titles)
        self.assertNotIn('Dashboard de gastos', titles)

    def test_approver_sees_approval_and_analytics(self):
        titles = {section['title'] for section in
                  self._navigation_as('group_expense_budget_approver')}
        self.assertIn('Aprobación de presupuestos', titles)
        self.assertIn('Proyectado vs. real', titles)
        self.assertIn('Dashboard de gastos', titles)
        self.assertNotIn('Importar Excel / CSV', titles)

    def test_manager_sees_all_sections(self):
        titles = {section['title'] for section in
                  self._navigation_as('group_expense_budget_manager')}
        self.assertIn('Configuración API de gastos', titles)
        self.assertIn('Presupuestos', titles)
        self.assertIn('Dashboard de gastos', titles)
