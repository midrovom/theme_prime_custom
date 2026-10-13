# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import AccessError, UserError, ValidationError


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

    def test_balance_and_execution_recompute_after_save_manual_actual(self):
        """Guardado manual: ambos indicadores se recalculan y persisten."""
        Line = self.env['expense.budget.line']
        line = Line.create({
            'budget_id': self.budget.id, 'account_id': self.account.id,
            'month': '9', 'planned_amount': 1000,
        })
        self.assertEqual(line.variance_amount, 1000)
        self.assertEqual(line.execution_percentage, 0)

        line.write({'actual_amount': 250})
        self.env.flush_all()
        line.invalidate_recordset(['actual_amount', 'variance_amount', 'execution_percentage'])
        self.assertEqual(line.actual_amount, 250)
        self.assertEqual(line.variance_amount, 750)
        self.assertEqual(line.execution_percentage, 25)

        line.write({'actual_amount': 400})
        self.env.flush_all()
        line.invalidate_recordset(['actual_amount', 'variance_amount', 'execution_percentage'])
        self.assertEqual(line.variance_amount, 600)
        self.assertEqual(line.execution_percentage, 40)

        # El cambio del proyectado también debe actualizar los indicadores.
        line.write({'planned_amount': 800})
        self.env.flush_all()
        line.invalidate_recordset(['variance_amount', 'execution_percentage'])
        self.assertEqual(line.variance_amount, 400)
        self.assertEqual(line.execution_percentage, 50)

    def test_budget_manager_multicompany_bypass_not_for_registrar(self):
        """El administrador no recibe la regla de compañía del módulo."""
        base = self.env.ref('base.group_user')
        manager_group = self.env.ref('expense_budget_control.group_expense_budget_manager')
        registrar_group = self.env.ref('expense_budget_control.group_expense_budget_registrar')
        company_b = self.env['res.company'].create({
            'name': 'Empresa secundaria de prueba presupuestaria',
            'currency_id': self.company.currency_id.id,
        })
        Users = self.env['res.users'].with_context(no_reset_password=True)
        manager = Users.create({
            'name': 'Administrador multiempresa de prueba',
            'login': 'test_budget_manager_company_all_147',
            'groups_id': [(6, 0, [base.id, manager_group.id])],
            'company_id': self.company.id,
            'company_ids': [(6, 0, [self.company.id])],
        })
        registrar = Users.create({
            'name': 'Registro limitado por empresa',
            'login': 'test_budget_registrar_company_only_147',
            'groups_id': [(6, 0, [base.id, registrar_group.id])],
            'company_id': self.company.id,
            'company_ids': [(6, 0, [self.company.id])],
        })
        Budget = self.env['expense.budget']
        created = Budget.with_user(manager).create({
            'name': 'Presupuesto empresa secundaria', 'year': 2035,
            'company_id': company_b.id,
        })
        self.assertIn(created.id, Budget.with_user(manager).search([]).ids)
        self.assertNotIn(created.id, Budget.with_user(registrar).search([]).ids)
        with self.assertRaises(AccessError):
            Budget.with_user(registrar).create({
                'name': 'Registro en empresa no autorizada', 'year': 2036,
                'company_id': company_b.id,
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

        # El aprobador no puede ver borradores ni sus líneas, ni siquiera
        # mediante búsqueda directa o apertura por ID.
        approver_budgets = self.env['expense.budget'].with_user(approver)
        approver_lines = self.env['expense.budget.line'].with_user(approver)
        self.assertNotIn(budget.id, approver_budgets.search([]).ids)
        self.assertNotIn(line.id, approver_lines.search([]).ids)
        with self.assertRaises(AccessError):
            budget.with_user(approver).read(['name'])
        with self.assertRaises(AccessError):
            line.with_user(approver).read(['planned_amount'])
        with self.assertRaises(AccessError):
            budget.with_user(approver).action_approve()  # Borrador no visible.

        budget.with_user(registrar).action_submit()
        self.assertEqual(budget.state, 'to_approve')
        self.assertIn(budget.id, approver_budgets.search([]).ids)
        self.assertIn(line.id, approver_lines.search([]).ids)
        with self.assertRaises(UserError):
            line.with_user(registrar).write({'planned_amount': 700})
        budget.with_user(approver).action_approve()
        self.assertEqual(budget.state, 'approved')
        self.assertIn(budget.id, approver_budgets.search([]).ids)
        self.assertIn(line.id, approver_lines.search([]).ids)
        with self.assertRaises(UserError):
            line.with_user(registrar).write({'planned_amount': 700})
        with self.assertRaises(AccessError):
            budget.with_user(approver).action_reopen()
        self.assertEqual(
            [state[0] for state in budget._fields['state'].selection],
            ['draft', 'to_approve', 'approved'],
        )

        wizard = self.env['expense.budget.import.wizard'].with_user(registrar).create({
            'import_type': 'expenses', 'company_id': self.company.id,
        })
        with self.assertRaises(AccessError):
            wizard.action_import()

    def test_manager_can_see_draft_even_with_approver_role(self):
        base_group = self.env.ref('base.group_user')
        manager_group = self.env.ref('expense_budget_control.group_expense_budget_manager')
        approver_group = self.env.ref('expense_budget_control.group_expense_budget_approver')
        manager = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Administrador y aprobador de prueba',
            'login': 'test_expense_budget_manager_with_approver',
            'groups_id': [(6, 0, [base_group.id, manager_group.id, approver_group.id])],
            'company_id': self.company.id,
            'company_ids': [(6, 0, [self.company.id])],
        })
        self.assertIn(
            self.budget.id,
            self.env['expense.budget'].with_user(manager).search([]).ids,
        )

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

    def test_only_three_states_and_new_rubro_after_approval(self):
        """Se habilita el siguiente rubro cuando el anterior se aprueba."""
        Budget = self.env['expense.budget']
        Line = self.env['expense.budget.line']
        states = [value for value, _name in Budget._fields['state'].selection]
        self.assertEqual(states, ['draft', 'to_approve', 'approved'])

        original_line = Line.create({
            'budget_id': self.budget.id, 'account_id': self.account.id,
            'month': '1', 'planned_amount': 500,
        })
        with self.assertRaises(UserError):
            Budget.create({
                'name': 'Otro rubro prematuro', 'year': 2026,
                'company_id': self.company.id,
            })
        self.budget.action_submit()
        self.assertEqual(self.budget.state, 'to_approve')
        with self.assertRaises(UserError):
            Budget.create({
                'name': 'Otro rubro pendiente', 'year': 2026,
                'company_id': self.company.id,
            })
        self.budget.action_approve()
        self.assertEqual(self.budget.state, 'approved')

        new_category = self.env['expense.budget.category'].create({
            'code': 'NEW-TEST', 'name': 'Nuevo rubro',
            'company_id': self.company.id,
        })
        new_account = self.env['expense.budget.account'].create({
            'code': '6002-TEST', 'name': 'Nueva cuenta',
            'category_id': new_category.id, 'company_id': self.company.id,
        })
        second_budget = Budget.create({
            'name': 'Presupuesto nuevo rubro', 'year': 2026,
            'company_id': self.company.id,
        })
        self.assertEqual(second_budget.state, 'draft')
        second_line = Line.create({
            'budget_id': second_budget.id, 'account_id': new_account.id,
            'month': '1', 'planned_amount': 300,
        })
        expense = self.env['expense.budget.expense'].create({
            'company_id': self.company.id, 'account_id': new_account.id,
            'date': '2026-01-18', 'description': 'Consumo del nuevo rubro',
            'amount': 75,
        })
        self.assertEqual(expense.budget_line_id, second_line)
        self.assertEqual(second_line.actual_amount, 75)
        self.assertEqual(original_line.actual_amount, 0)

        with self.assertRaises(ValidationError):
            Line.create({
                'budget_id': second_budget.id, 'account_id': self.account.id,
                'month': '1', 'planned_amount': 100,
            })

    def test_comparison_pdf_groups_accounts_and_calculates_weighted_execution(self):
        """El PDF del comparativo agrupa rubro/cuenta sin promediar porcentajes."""
        water = self.env['expense.budget.account'].create({
            'code': '6001-TEST-PDF', 'name': 'Agua',
            'category_id': self.category.id, 'company_id': self.company.id,
        })
        self.env['expense.budget.line'].create({
            'budget_id': self.budget.id, 'account_id': self.account.id,
            'month': '1', 'planned_amount': 100,
        }).write({'actual_amount': 50})
        self.env['expense.budget.line'].create({
            'budget_id': self.budget.id, 'account_id': water.id,
            'month': '2', 'planned_amount': 300,
        }).write({'actual_amount': 75})

        wizard = self.env['expense.budget.comparison.report.wizard'].create({
            'company_id': self.company.id, 'year': 2026,
        })
        report = self.env['report.expense_budget_control.report_comparison_document']
        prepared = report._get_report_values([wizard.id])['reports'][0]
        self.assertEqual(len(prepared['categories']), 1)
        self.assertEqual(len(prepared['categories'][0]['accounts']), 2)
        # Debajo de cada cuenta debe imprimirse la línea individual,
        # con presupuesto, empresa, rubro, mes y sus cuatro indicadores.
        group = prepared['categories'][0]
        self.assertEqual(group['line_count'], 2)
        self.assertEqual(sum(acc['line_count'] for acc in group['accounts']), 2)
        self.assertEqual(sum(len(acc['lines']) for acc in group['accounts']), 2)
        self.assertEqual(
            sorted(detail['month_name'] for acc in group['accounts'] for detail in acc['lines']),
            ['Enero', 'Febrero'],
        )
        for acc in group['accounts']:
            detail = acc['lines'][0]
            self.assertEqual(detail['line'].budget_id, self.budget)
            self.assertEqual(detail['line'].company_id, self.company)
            self.assertEqual(detail['line'].category_id, self.category)
            self.assertEqual(detail['line'].account_id, acc['account'])
        self.assertEqual(prepared['grand_total']['planned'], 400)
        self.assertEqual(prepared['grand_total']['actual'], 125)
        self.assertEqual(prepared['grand_total']['available'], 275)
        self.assertAlmostEqual(prepared['grand_total']['execution'], 31.25)
        self.assertEqual(wizard.action_print_pdf()['type'], 'ir.actions.report')

        filtered = self.env['expense.budget.comparison.report.wizard'].create({
            'company_id': self.company.id, 'year': 2026,
            'category_id': self.category.id, 'account_id': water.id,
        })
        data = report._get_report_values([filtered.id])['reports'][0]
        self.assertEqual(len(data['categories'][0]['accounts']), 1)
        self.assertEqual(data['grand_total']['actual'], 75)

    def test_comparison_pdf_approver_cannot_see_draft_lines(self):
        """Imprimir no debe permitir eludir la regla de solo enviados/aprobados."""
        self.env['expense.budget.line'].create({
            'budget_id': self.budget.id, 'account_id': self.account.id,
            'month': '3', 'planned_amount': 750,
        })
        approver_group = self.env.ref('expense_budget_control.group_expense_budget_approver')
        internal_group = self.env.ref('base.group_user')
        approver = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Aprobador comprobación PDF',
            'login': 'test_budget_approver_pdf_1411',
            'company_id': self.company.id,
            'company_ids': [(6, 0, [self.company.id])],
            'groups_id': [(6, 0, [internal_group.id, approver_group.id])],
        })
        wizard = self.env['expense.budget.comparison.report.wizard'].with_user(approver).create({
            'company_id': self.company.id, 'year': 2026,
        })
        report = self.env['report.expense_budget_control.report_comparison_document'].with_user(approver)
        self.assertEqual(report._prepare_comparison(wizard)['line_count'], 0)
        self.budget.action_submit()
        self.assertEqual(report._prepare_comparison(wizard)['line_count'], 1)
