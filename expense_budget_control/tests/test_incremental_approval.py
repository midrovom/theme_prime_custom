# -*- coding: utf-8 -*-
"""Pruebas de aprobación por lotes y bloqueo de proyecciones aprobadas."""
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestIncrementalBudgetApproval(TransactionCase):

    def setUp(self):
        super().setUp()
        self.company = self.env.company
        self.category = self.env['expense.budget.category'].create({
            'code': 'TEST-INCR-APPROVAL',
            'name': 'Servicios básicos - aprobación por etapas',
            'company_id': self.company.id,
        })
        self.account = self.env['expense.budget.account'].create({
            'code': 'TEST-INCR-AGUA', 'name': 'Agua',
            'category_id': self.category.id, 'company_id': self.company.id,
        })
        self.budget = self.env['expense.budget'].with_context(
            skip_expense_budget_consumption_on_save=True,
        ).create({
            'name': 'Presupuesto de prueba por etapas',
            'year': 2097, 'company_id': self.company.id,
            'category_id': self.category.id,
        })
        self.Line = self.env['expense.budget.line'].with_context(
            skip_expense_budget_consumption_on_save=True,
        )
        self.initial_lines = self.Line.create([
            {
                'budget_id': self.budget.id, 'account_id': self.account.id,
                'month': str(month), 'planned_amount': 100.0,
            }
            for month in range(1, 6)
        ])

        base_group = self.env.ref('base.group_user')
        registrar_group = self.env.ref('expense_budget_control.group_expense_budget_registrar')
        approver_group = self.env.ref('expense_budget_control.group_expense_budget_approver')
        Users = self.env['res.users'].with_context(no_reset_password=True)
        self.registrar = Users.create({
            'name': 'Registrador incremental test',
            'login': 'test_incremental_budget_registrar_2097',
            'groups_id': [(6, 0, [base_group.id, registrar_group.id])],
            'company_id': self.company.id,
            'company_ids': [(6, 0, [self.company.id])],
        })
        self.approver = Users.create({
            'name': 'Aprobador incremental test',
            'login': 'test_incremental_budget_approver_2097',
            'groups_id': [(6, 0, [base_group.id, approver_group.id])],
            'company_id': self.company.id,
            'company_ids': [(6, 0, [self.company.id])],
        })

    def _approve_initial_budget(self):
        self.budget.with_user(self.registrar).action_submit()
        self.budget.with_user(self.approver).action_approve()
        self.assertEqual(self.budget.state, 'approved')
        self.assertTrue(all(line.approval_state == 'approved' for line in self.initial_lines))
        self.assertEqual(self.budget.approved_through_month, '5')

    def test_add_and_approve_future_months_without_changing_approved_lines(self):
        self._approve_initial_budget()
        original_amounts = self.initial_lines.mapped('planned_amount')

        # Simula el guardado del One2many desde la ficha de presupuesto aprobada.
        self.budget.with_user(self.registrar).with_context(
            skip_expense_budget_consumption_on_save=True,
        ).write({
            'line_ids': [(0, 0, {
                'account_id': self.account.id,
                'month': '6',
                'planned_amount': 150.0,
            })],
        })
        june_line = self.budget.line_ids.filtered(lambda line: line.month == '6')
        self.assertEqual(len(june_line), 1)
        self.assertEqual(june_line.approval_state, 'draft')
        self.assertEqual(self.budget.state, 'approved')
        self.assertEqual(self.budget.approved_through_month, '5')
        self.assertEqual(self.budget.months_pending_approval, 'Junio')

        with self.assertRaises(UserError):
            self.initial_lines[0].with_user(self.registrar).write({'planned_amount': 999.0})

        # La proyección futura sí puede corregirse antes de enviarse.
        june_line.with_user(self.registrar).write({'planned_amount': 175.0})
        self.budget.with_user(self.registrar).action_submit()
        self.assertEqual(self.budget.state, 'to_approve')
        self.assertTrue(all(line.approval_state == 'approved' for line in self.initial_lines))
        self.assertEqual(june_line.approval_state, 'to_approve')

        self.budget.with_user(self.approver).action_approve()
        self.assertEqual(self.budget.state, 'approved')
        self.assertTrue(all(line.approval_state == 'approved' for line in self.budget.line_ids))
        self.assertEqual(self.budget.approved_through_month, '6')
        self.assertFalse(self.budget.months_pending_approval)
        self.assertEqual(self.initial_lines.mapped('planned_amount'), original_amounts)

    def test_rejecting_incremental_batch_preserves_prior_approval(self):
        self._approve_initial_budget()
        self.budget.with_user(self.registrar).with_context(
            skip_expense_budget_consumption_on_save=True,
        ).write({
            'line_ids': [(0, 0, {
                'account_id': self.account.id,
                'month': '6',
                'planned_amount': 200.0,
            })],
        })
        june_line = self.budget.line_ids.filtered(lambda line: line.month == '6')
        self.budget.with_user(self.registrar).action_submit()
        self.budget.with_user(self.approver).action_reject()

        self.assertEqual(self.budget.state, 'approved')
        self.assertTrue(all(line.approval_state == 'approved' for line in self.initial_lines))
        self.assertEqual(june_line.approval_state, 'rejected')
        self.assertEqual(self.budget.approved_through_month, '5')
        self.assertEqual(self.budget.months_pending_approval, 'Junio')

        # El lote rechazado queda corregible y puede reenviarse.
        june_line.with_user(self.registrar).write({'planned_amount': 220.0})
        self.budget.with_user(self.registrar).action_submit()
        self.assertEqual(june_line.approval_state, 'to_approve')


    def test_annual_amount_is_divided_by_twelve_and_reused_for_future_months(self):
        january = self.initial_lines.filtered(lambda line: line.month == '1')
        january.write({'annual_amount': 1200.0, 'planned_amount': 999.0})
        self.assertEqual(january.annual_amount, 1200.0)
        self.assertEqual(january.planned_amount, 100.0)
        self.assertTrue(all(line.annual_amount == 1200.0 for line in self.initial_lines))
        self.assertTrue(all(line.planned_amount == 100.0 for line in self.initial_lines))

        # Before any month is approved, changing the annual target aligns all
        # unapproved months for the same account and center.
        january.write({'annual_amount': 2400.0})
        self.assertTrue(all(line.annual_amount == 2400.0 for line in self.initial_lines))
        self.assertTrue(all(line.planned_amount == 200.0 for line in self.initial_lines))

        self._approve_initial_budget()
        june = self.Line.create({
            'budget_id': self.budget.id,
            'account_id': self.account.id,
            'month': '6',
        })
        self.assertEqual(june.annual_amount, 2400.0)
        self.assertEqual(june.planned_amount, 200.0)
        self.assertEqual(june.approval_state, 'draft')

    def test_header_annual_target_populates_monthly_projections(self):
        target = self.env['expense.budget.annual.target'].with_context(
            skip_expense_budget_consumption_on_save=True,
        ).create({
            'budget_id': self.budget.id,
            'account_id': self.account.id,
            'annual_amount': 1200.0,
        })
        self.assertEqual(target.monthly_amount, 100.0)
        self.assertTrue(all(line.planned_amount == 100.0 for line in self.initial_lines))
        self.assertTrue(all(line.annual_amount == 1200.0 for line in self.initial_lines))

        # Any following month inherits the annual target from the budget header.
        june = self.Line.create({
            'budget_id': self.budget.id,
            'account_id': self.account.id,
            'month': '6',
        })
        self.assertEqual(june.annual_amount, 1200.0)
        self.assertEqual(june.planned_amount, 100.0)

    def test_header_annual_target_does_not_change_approved_months(self):
        target = self.env['expense.budget.annual.target'].create({
            'budget_id': self.budget.id,
            'account_id': self.account.id,
            'annual_amount': 1200.0,
        })
        self._approve_initial_budget()
        original_amounts = self.initial_lines.mapped('planned_amount')
        with self.assertRaises(UserError):
            target.write({'annual_amount': 1800.0})
        june = self.Line.create({
            'budget_id': self.budget.id,
            'account_id': self.account.id,
            'month': '6',
        })
        self.assertEqual(june.planned_amount, 100.0)
        self.assertEqual(self.initial_lines.mapped('planned_amount'), original_amounts)

    def test_annual_amount_cannot_be_changed_after_pair_is_approved(self):
        self._approve_initial_budget()
        annual_account = self.env['expense.budget.account'].create({
            'code': 'TEST-INCR-ANNUAL-AGUA', 'name': 'Agua presupuesto anual',
            'category_id': self.category.id, 'company_id': self.company.id,
        })
        january = self.Line.create({
            'budget_id': self.budget.id, 'account_id': annual_account.id,
            'month': '1', 'annual_amount': 1200.0,
        })
        self.budget.with_context(skip_expense_budget_consumption_on_save=True).action_submit()
        self.budget.sudo().action_approve()
        june = self.Line.create({
            'budget_id': self.budget.id, 'account_id': annual_account.id,
            'month': '6', 'annual_amount': 1200.0,
        })
        self.assertEqual(june.planned_amount, 100.0)
        with self.assertRaises(UserError):
            june.write({'annual_amount': 1800.0})

    def test_cannot_add_new_line_in_an_already_approved_month(self):
        self._approve_initial_budget()
        with self.assertRaises(UserError):
            self.Line.with_user(self.registrar).create({
                'budget_id': self.budget.id,
                'account_id': self.account.id,
                'month': '5',
                'planned_amount': 100.0,
            })
