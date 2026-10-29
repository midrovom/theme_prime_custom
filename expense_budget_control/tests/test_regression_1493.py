# -*- coding: utf-8 -*-
"""Regresión: el total de las proyecciones coincide con el importe anual."""
from odoo.tests.common import TransactionCase, tagged
from ..models.budget import exact_budget_allocation


@tagged('post_install', '-at_install')
class TestExactAnnualDistribution1493(TransactionCase):

    def test_exact_allocation_two_digits(self):
        for amount, count in [(1400, 12), (1300, 12), (1200, 12), (1, 12), (1400, 3)]:
            values = exact_budget_allocation(amount, count, 2)
            self.assertEqual(len(values), count)
            self.assertEqual(round(sum(values), 2), round(amount, 2))
        self.assertEqual(exact_budget_allocation(1400, 12, 2).count(116.67), 8)
        self.assertEqual(exact_budget_allocation(1300, 12, 2).count(108.34), 4)

    def test_precision_four_and_six(self):
        for digits in (4, 6):
            values = exact_budget_allocation(1, 12, digits)
            self.assertEqual(round(sum(values), digits), 1)

    def test_registered_views_have_no_old_labels(self):
        list_view = self.env.ref('expense_budget_control.view_expense_budget_list')
        form_view = self.env.ref('expense_budget_control.view_expense_budget_form')
        self.assertNotIn('Meses pendientes', list_view.arch_db)
        self.assertNotIn('Agregar distribuye el importe', form_view.arch_db)


@tagged('post_install', '-at_install')
class TestExactAnnualDistributionWorkflow1493(TransactionCase):
    def setUp(self):
        super().setUp()
        self.company = self.env.company
        self.category = self.env['expense.budget.category'].create({
            'name': 'Rubro test 1493', 'code': 'RB-1493',
            'company_id': self.company.id,
        })
        self.account = self.env['expense.budget.account'].create({
            'name': 'Internet test 1493', 'code': 'NET-1493',
            'category_id': self.category.id, 'company_id': self.company.id,
        })
        self.center = self.env['expense.budget.cost.center'].create({
            'name': 'Quito 1493', 'code': 'QUI-1493',
            'company_id': self.company.id,
        })
        self.budget = self.env['expense.budget'].with_context(
            skip_expense_budget_consumption_on_save=True,
        ).create({
            'name': 'Prueba exacta 1493', 'year': 2094,
            'category_id': self.category.id, 'company_id': self.company.id,
        })
        group = self.env.ref('expense_budget_control.group_expense_budget_registrar')
        self.registrar = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Registro de distribución 1493',
            'login': 'registro_1493_presupuesto',
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id, group.id])],
            'company_id': self.company.id,
            'company_ids': [(6, 0, [self.company.id])],
        })

    def _record(self, amount, month_ids=False):
        budget = self.budget.with_user(self.registrar).with_context(
            skip_expense_budget_consumption_on_save=True,
        )
        budget.write({
            'quick_account_id': self.account.id,
            'quick_cost_center_id': self.center.id,
            'quick_month_ids': [(6, 0, month_ids)] if month_ids else [(5, 0, 0)],
            'quick_annual_amount': amount,
        })
        budget.action_add_quick_monthly_lines()
        return self.budget.line_ids.sorted(lambda row: int(row.month))

    def test_full_year_no_cents_difference(self):
        original_precision = self.env.ref('expense_budget_control.expense_budget_amount_precision')
        previous = original_precision.digits
        try:
            original_precision.sudo().write({'digits': 2})
            lines = self._record(1400)
            self.assertEqual(len(lines), 12)
            self.assertEqual(round(sum(lines.mapped('planned_amount')), 2), 1400)
            self.assertEqual(round(self.budget.planned_amount, 2), 1400)
            self.assertEqual(len(set(lines.mapped('planned_amount'))), 2)
            # Repeating the reconciliation must be idempotent.
            self.budget.annual_target_ids._rebalance_exact_distribution()
            self.assertEqual(round(self.budget.planned_amount, 2), 1400)
        finally:
            original_precision.sudo().write({'digits': previous})

    def test_approved_budget_stays_unchanged(self):
        lines = self._record(1300)
        prior = [(line.id, line.planned_amount) for line in lines]
        self.budget.sudo().write({'state': 'approved'})
        self.budget.annual_target_ids._rebalance_exact_distribution()
        self.assertEqual(prior, [(line.id, line.planned_amount) for line in lines])
