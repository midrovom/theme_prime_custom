# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import AccessError, UserError


@tagged('post_install', '-at_install')
class TestExpenseBudget(TransactionCase):

    def setUp(self):
        super().setUp()
        self.company = self.env.company
        self.category = self.env['expense.budget.category'].create({
            'code': 'ADM-TEST', 'name': 'Administración', 'company_id': self.company.id,
        })
        self.account = self.env['expense.budget.account'].create({
            'code': '6000-TEST', 'name': 'Servicios', 'category_id': self.category.id,
            'company_id': self.company.id,
        })
        self.budget = self.env['expense.budget'].create({
            'name': 'Test presupuestario', 'year': 2026, 'company_id': self.company.id,
        })

    def test_planned_vs_actual(self):
        line = self.env['expense.budget.line'].create({
            'budget_id': self.budget.id, 'account_id': self.account.id,
            'month': '10', 'planned_amount': 1000,
        })
        movement = self.env['expense.budget.expense'].create({
            'company_id': self.company.id, 'account_id': self.account.id,
            'date': '2026-10-01', 'description': 'Licencias', 'amount': 250,
        })
        self.assertEqual(movement.budget_line_id, line)
        self.assertEqual(line.actual_amount, 250)
        self.assertEqual(line.variance_amount, 750)
        self.assertEqual(self.budget.actual_amount, 250)
        movement.write({'amount': 300})
        self.assertEqual(line.actual_amount, 300)
        movement.unlink()
        self.assertEqual(line.actual_amount, 0)

    def test_reconcile_expense_created_before_line(self):
        expense = self.env['expense.budget.expense'].create({
            'company_id': self.company.id, 'account_id': self.account.id,
            'date': '2026-02-17', 'description': 'Reparación', 'amount': 80,
        })
        self.assertFalse(expense.budget_line_id)
        line = self.env['expense.budget.line'].create({
            'budget_id': self.budget.id, 'account_id': self.account.id,
            'month': '2', 'planned_amount': 100,
        })
        self.assertEqual(expense.budget_line_id, line)
        self.assertEqual(line.actual_amount, 80)

    def test_idempotent_import_and_reversal(self):
        data = {'codigo_cuenta': '6000-TEST', 'fecha': '2026-10-12',
                'monto': '125,50', 'descripcion': 'Energía'}
        Expense = self.env['expense.budget.expense']
        self.assertEqual(Expense._upsert_external(self.company, data, 'excel', 'INV-101'), 'created')
        self.assertEqual(Expense._upsert_external(self.company, data, 'excel', 'INV-101'), 'unchanged')
        self.assertEqual(Expense.search_count([('source_key', '=', 'excel:INV-101')]), 1)
        data['monto'] = '-20'
        self.assertEqual(Expense._upsert_external(self.company, data, 'excel', 'INV-101'), 'updated')

    def test_budget_approval_locks_lines(self):
        line = self.env['expense.budget.line'].create({
            'budget_id': self.budget.id, 'account_id': self.account.id,
            'month': '1', 'planned_amount': 500,
        })
        self.budget.action_submit()
        self.budget.action_approve()
        with self.assertRaises(UserError):
            line.write({'planned_amount': 600})

    def test_annual_pdf_grouped_by_category_account_and_month(self):
        self.category.write({'name': 'Servicios básicos'})
        water = self.env['expense.budget.account'].create({
            'code': '6001-TEST', 'name': 'Agua', 'category_id': self.category.id,
            'company_id': self.company.id,
        })
        self.account.write({'name': 'Luz'})
        january_light = self.env['expense.budget.line'].create({
            'budget_id': self.budget.id, 'account_id': self.account.id,
            'month': '1', 'planned_amount': 100,
        })
        self.env['expense.budget.line'].create({
            'budget_id': self.budget.id, 'account_id': water.id,
            'month': '1', 'planned_amount': 200,
        })
        self.env['expense.budget.expense'].create({
            'company_id': self.company.id, 'account_id': self.account.id,
            'date': '2026-01-10', 'description': 'Electricidad', 'amount': 25,
        })
        self.env['expense.budget.expense'].create({
            'company_id': self.company.id, 'account_id': water.id,
            'date': '2026-01-12', 'description': 'Agua potable', 'amount': 50,
        })

        report = self.env['report.expense_budget_control.report_annual_budget_document']
        values = report._get_report_values([self.budget.id])
        self.assertEqual(len(values['reports']), 1)
        result = values['reports'][0]
        self.assertEqual(len(result['quarters']), 4)
        self.assertEqual(len(result['months']), 12)
        self.assertEqual(result['months'][11]['name'], 'Diciembre')
        self.assertEqual(result['quarters'][0]['months'][0]['name'], 'Enero')
        self.assertEqual(len(result['categories']), 1)
        category = result['categories'][0]
        self.assertEqual(category['category'].name, 'Servicios básicos')
        self.assertEqual({a['account'].name for a in category['accounts']}, {'Luz', 'Agua'})
        self.assertEqual(category['months']['1']['planned'], 300)
        self.assertEqual(category['months']['1']['actual'], 75)
        self.assertEqual(category['months']['1']['execution'], 25)
        self.assertEqual(result['totals']['1']['execution'], 25)
        self.assertEqual(category['annual']['planned'], 300)
        self.assertEqual(category['annual']['actual'], 75)
        self.assertEqual(category['annual']['execution'], 25)
        self.assertEqual(result['annual_total']['execution'], 25)
        self.assertEqual(january_light.execution_percentage, 25)
        self.assertFalse(result['totals']['2']['has_line'])

        action = self.budget.action_print_annual_pdf()
        self.assertEqual(action['type'], 'ir.actions.report')
        self.assertEqual(action['report_name'],
                         'expense_budget_control.report_annual_budget_document')

    def test_annual_report_uses_weighted_total_for_percentage(self):
        self.env['expense.budget.line'].create({
            'budget_id': self.budget.id, 'account_id': self.account.id,
            'month': '1', 'planned_amount': 100,
        })
        self.env['expense.budget.line'].create({
            'budget_id': self.budget.id, 'account_id': self.account.id,
            'month': '2', 'planned_amount': 300,
        })
        self.env['expense.budget.expense'].create({
            'company_id': self.company.id, 'account_id': self.account.id,
            'date': '2026-01-07', 'description': 'Gasto 1', 'amount': 100,
        })
        self.env['expense.budget.expense'].create({
            'company_id': self.company.id, 'account_id': self.account.id,
            'date': '2026-02-07', 'description': 'Gasto 2', 'amount': 60,
        })
        report = self.env['report.expense_budget_control.report_annual_budget_document']
        result = report._get_report_values([self.budget.id])['reports'][0]
        self.assertEqual(result['totals']['1']['execution'], 100)
        self.assertEqual(result['totals']['2']['execution'], 20)
        self.assertEqual(result['annual_total']['execution'], 40)
        self.assertEqual(result['categories'][0]['annual']['execution'], 40)
        self.assertEqual(result['categories'][0]['accounts'][0]['annual']['execution'], 40)

    def test_separated_registration_and_approval_roles(self):
        base_group = self.env.ref('base.group_user')
        registrar_group = self.env.ref('expense_budget_control.group_expense_budget_registrar')
        approver_group = self.env.ref('expense_budget_control.group_expense_budget_approver')
        Users = self.env['res.users'].with_context(no_reset_password=True)
        registrar = Users.create({
            'name': 'Registrador de prueba', 'login': 'test_expense_budget_registrar',
            'groups_id': [(6, 0, [base_group.id, registrar_group.id])],
            'company_id': self.company.id,
            'company_ids': [(6, 0, [self.company.id])],
        })
        approver = Users.create({
            'name': 'Aprobador de prueba', 'login': 'test_expense_budget_approver',
            'groups_id': [(6, 0, [base_group.id, approver_group.id])],
            'company_id': self.company.id,
            'company_ids': [(6, 0, [self.company.id])],
        })
        budget = self.env['expense.budget'].with_user(registrar).create({
            'name': 'Presupuesto para aprobar', 'year': 2029,
            'company_id': self.company.id,
        })
        line = self.env['expense.budget.line'].with_user(registrar).create({
            'budget_id': budget.id, 'account_id': self.account.id,
            'month': '1', 'planned_amount': 500,
        })
        line.with_user(registrar).write({'planned_amount': 600})
        self.assertEqual(line.planned_amount, 600)

        with self.assertRaises(AccessError):
            budget.with_user(registrar).action_approve()
        with self.assertRaises(AccessError):
            budget.with_user(registrar).write({'state': 'approved'})
        with self.assertRaises(UserError):
            self.env['expense.budget'].with_user(registrar).create({
                'name': 'Alta directa aprobada', 'year': 2031,
                'company_id': self.company.id, 'state': 'approved',
            })
        with self.assertRaises(AccessError):
            budget.with_user(approver).write({'name': 'Alteración no permitida'})
        with self.assertRaises(AccessError):
            line.with_user(approver).write({'planned_amount': 800})
        with self.assertRaises(AccessError):
            budget.with_user(approver).create({
                'name': 'No debe crear', 'year': 2030,
                'company_id': self.company.id,
            })

        with self.assertRaises(UserError):
            budget.with_user(approver).action_approve()  # Aún no se envió.
        budget.with_user(registrar).action_submit()
        self.assertEqual(budget.state, 'to_approve')
        with self.assertRaises(UserError):
            line.with_user(registrar).write({'planned_amount': 700})
        budget.with_user(approver).action_approve()
        self.assertEqual(budget.state, 'approved')
        with self.assertRaises(UserError):
            line.with_user(registrar).write({'planned_amount': 700})
        with self.assertRaises(AccessError):
            budget.with_user(approver).action_reopen()
        with self.assertRaises(AccessError):
            budget.with_user(registrar).action_close()

        wizard = self.env['expense.budget.import.wizard'].with_user(registrar).create({
            'import_type': 'expenses', 'company_id': self.company.id,
        })
        with self.assertRaises(AccessError):
            wizard.action_import()

    def test_registrar_can_enter_and_correct_consumed_without_removing(self):
        """Registro administra consumos manuales, no aprobaciones ni bajas."""
        base_group = self.env.ref('base.group_user')
        registrar_group = self.env.ref('expense_budget_control.group_expense_budget_registrar')
        registrar = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Registrador de gastos prueba',
            'login': 'test_expense_budget_registrar_actual',
            'groups_id': [(6, 0, [base_group.id, registrar_group.id])],
            'company_id': self.company.id,
            'company_ids': [(6, 0, [self.company.id])],
        })
        line = self.env['expense.budget.line'].create({
            'budget_id': self.budget.id, 'account_id': self.account.id,
            'month': '10', 'planned_amount': 500,
        })
        self.budget.action_submit()
        self.budget.action_approve()
        expense = self.env['expense.budget.expense'].with_user(registrar).create({
            'company_id': self.company.id, 'account_id': self.account.id,
            'date': '2026-10-13', 'description': 'Consumo registrado manualmente',
            'amount': 100,
        })
        self.assertEqual(expense.source, 'manual')
        self.assertEqual(expense.budget_line_id, line)
        self.assertEqual(line.actual_amount, 100)
        self.assertEqual(line.execution_percentage, 20)
        expense.write({'amount': 150})
        self.assertEqual(line.actual_amount, 150)
        self.assertEqual(line.variance_amount, 350)
        with self.assertRaises(AccessError):
            expense.unlink()
        with self.assertRaises(AccessError):
            self.budget.with_user(registrar).action_approve()

    def test_registrar_edits_monthly_consumed_and_submits_to_approver(self):
        """Consumido editable y enviado a aprobación, sin tocar gastos API."""
        base_group = self.env.ref('base.group_user')
        registrar_group = self.env.ref('expense_budget_control.group_expense_budget_registrar')
        approver_group = self.env.ref('expense_budget_control.group_expense_budget_approver')
        Users = self.env['res.users'].with_context(no_reset_password=True)
        registrar = Users.create({
            'name': 'Registro consumido editable',
            'login': 'test_budget_registro_manual_143',
            'groups_id': [(6, 0, [base_group.id, registrar_group.id])],
            'company_id': self.company.id,
            'company_ids': [(6, 0, [self.company.id])],
        })
        approver = Users.create({
            'name': 'Aprobación presupuesto 143',
            'login': 'test_budget_approver_143',
            'groups_id': [(6, 0, [base_group.id, approver_group.id])],
            'company_id': self.company.id,
            'company_ids': [(6, 0, [self.company.id])],
        })
        line = self.env['expense.budget.line'].create({
            'budget_id': self.budget.id, 'account_id': self.account.id,
            'month': '3', 'planned_amount': 600,
        })
        # Consumo ingresado directamente por el registrador en la proyección.
        line.with_user(registrar).write({'actual_amount': 150})
        self.assertEqual(line.actual_amount, 150)
        self.assertEqual(self.budget.actual_amount, 150)
        self.assertEqual(line.variance_amount, 450)
        self.assertEqual(line.execution_percentage, 25)

        # Un movimiento de API sigue contabilizándose sin borrarse ni alterarse.
        expense = self.env['expense.budget.expense'].create({
            'company_id': self.company.id, 'account_id': self.account.id,
            'date': '2026-03-10', 'description': 'API existente',
            'amount': 40, 'source': 'api', 'source_key': 'api:143:check',
        })
        self.assertEqual(line.actual_amount, 190)
        self.assertEqual(expense.amount, 40)
        self.assertEqual(line.manual_actual_amount, 150)

        self.budget.with_user(registrar).action_submit()
        self.assertEqual(self.budget.state, 'to_approve')
        with self.assertRaises(UserError):
            self.budget.with_user(registrar).write({'name': 'No editable'})
        with self.assertRaises(UserError):
            self.budget.with_user(registrar).write({
                'line_ids': [(1, line.id, {'planned_amount': 900})],
            })
        # Verifica la vía de guardado de la tabla One2many en el formulario.
        self.budget.with_user(registrar).write({
            'line_ids': [(1, line.id, {'actual_amount': 250})],
        })
        self.assertEqual(line.actual_amount, 250)
        self.assertEqual(expense.amount, 40)
        self.assertEqual(line.manual_actual_amount, 210)

        with self.assertRaises(AccessError):
            self.budget.with_user(registrar).action_approve()
        self.budget.with_user(approver).action_approve()
        self.assertEqual(self.budget.state, 'approved')
        self.budget.with_user(registrar).write({
            'line_ids': [(1, line.id, {'actual_amount': 280})],
        })
        self.assertEqual(line.actual_amount, 280)
        self.assertEqual(self.budget.actual_amount, 280)
