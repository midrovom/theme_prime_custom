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
        # El PDF anual presenta detalle por presupuesto/cuenta/año, sin
        # repetir los meses como detalle independiente.
        group = prepared['categories'][0]
        self.assertEqual(group['line_count'], 2)
        self.assertEqual(sum(acc['line_count'] for acc in group['accounts']), 2)
        self.assertEqual(prepared['account_count'], 2)
        self.assertEqual(
            {acc['account'].id for acc in group['accounts']},
            {self.account.id, water.id},
        )
        self.assertEqual(sum(len(acc['lines']) for acc in group['accounts']), 2)
        self.assertTrue(all(annual.budget_id == self.budget
                            for acc in group['accounts'] for annual in acc['lines']))
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

    def test_comparison_report_year_selection(self):
        wizard_model = self.env['expense.budget.comparison.report.wizard']
        self.assertEqual(wizard_model._fields['year'].type, 'selection')
        self.assertIn(('2026', '2026'), wizard_model._selection_years())
        wizard = wizard_model.create({
            'company_id': self.company.id,
            'year': 2026,  # Compatibilidad con año entero de versiones anteriores.
        })
        self.assertEqual(wizard.year, '2026')
        report = self.env['report.expense_budget_control.report_comparison_document']
        result = report._prepare_comparison(wizard)
        self.assertEqual(result['wizard'].year, '2026')

    def test_comparison_pdf_category_only_includes_all_accounts_and_budgets(self):
        """Solo Rubro: todas las cuentas y presupuestos del año, sin filtrar cuenta."""
        Account = self.env['expense.budget.account']
        Line = self.env['expense.budget.line']
        agua = Account.create({
            'code': 'PDF-AGUA-ALL', 'name': 'Agua',
            'company_id': self.company.id, 'category_id': self.category.id,
        })
        # Primer presupuesto: dos cuentas bajo el mismo rubro.
        luz_enero = Line.create({
            'budget_id': self.budget.id, 'account_id': self.account.id,
            'month': '1', 'planned_amount': 100,
        })
        luz_enero.write({'actual_amount': 40})
        agua_enero = Line.create({
            'budget_id': self.budget.id, 'account_id': agua.id,
            'month': '1', 'planned_amount': 100,
        })
        agua_enero.write({'actual_amount': 10})
        self.budget.action_submit()
        self.budget.action_approve()

        # Segundo presupuesto aprobado o en borrador: debe aparecer también
        # cuando el administrador imprime todo el rubro.
        second = self.env['expense.budget'].create({
            'name': 'Segundo presupuesto del rubro', 'year': 2026,
            'company_id': self.company.id,
        })
        for account, month, planned, actual in (
                (self.account, '4', 100, 40),
                (self.account, '9', 50, 0),
                (agua, '6', 70, 30)):
            line = Line.create({
                'budget_id': second.id, 'account_id': account.id,
                'month': month, 'planned_amount': planned,
            })
            line.write({'actual_amount': actual})

        wizard = self.env['expense.budget.comparison.report.wizard'].create({
            'company_id': self.company.id, 'year': 2026,
            'category_id': self.category.id,
        })
        self.assertFalse(wizard.account_id)
        report = self.env['report.expense_budget_control.report_comparison_document']
        result = report._prepare_comparison(wizard)
        self.assertEqual(result['line_count'], 5)
        self.assertEqual(len(result['categories']), 1)
        group = result['categories'][0]
        self.assertEqual(group['line_count'], 5)
        self.assertEqual(len(group['accounts']), 2)
        accounts = {entry['account'].id: entry for entry in group['accounts']}
        self.assertEqual(accounts[self.account.id]['line_count'], 3)
        self.assertEqual(accounts[agua.id]['line_count'], 2)
        self.assertEqual(result['grand_total']['planned'], 420)
        self.assertEqual(result['grand_total']['actual'], 120)
        self.assertEqual(result['grand_total']['available'], 300)
        self.assertAlmostEqual(result['grand_total']['execution'], 120 / 420 * 100)
        # Cada cuenta se presenta una sola vez, acumulando todos sus meses
        # incluso cuando están distribuidos entre presupuestos del mismo año.
        self.assertEqual(result['account_count'], 2)
        self.assertEqual(result['budget_account_count'], 4)
        self.assertEqual(len(accounts[self.account.id]['lines']), 2)
        self.assertEqual(len(accounts[agua.id]['lines']), 2)
        # Cada línea visible es el acumulado ANUAL de una cuenta en un
        # presupuesto, no el detalle mensual original.
        luz_by_budget = {row.budget_id.id: row for row in accounts[self.account.id]['lines']}
        self.assertEqual(set(luz_by_budget), {self.budget.id, second.id})
        self.assertEqual(luz_by_budget[self.budget.id].planned_amount, 100)
        self.assertEqual(luz_by_budget[second.id].planned_amount, 150)
        self.assertEqual(luz_by_budget[second.id].actual_amount, 40)
        self.assertEqual(luz_by_budget[second.id].line_count, 2)
        self.assertTrue(all(row.year == 2026 for row in luz_by_budget.values()))
        self.assertEqual(accounts[self.account.id]['total']['planned'], 250)
        self.assertEqual(accounts[self.account.id]['total']['actual'], 80)
        self.assertEqual(accounts[agua.id]['total']['planned'], 170)
        self.assertEqual(accounts[agua.id]['total']['actual'], 40)

        # Cambiar el rubro no puede conservar el filtro por una cuenta anterior.
        wizard.account_id = agua
        wizard._onchange_category_id()
        self.assertFalse(wizard.account_id)
        self.assertEqual(report._prepare_comparison(wizard)['line_count'], 5)

        # Solo cuando se escoge explícitamente Cuenta se limita el reporte.
        wizard.account_id = agua
        self.assertEqual(report._prepare_comparison(wizard)['line_count'], 2)

    def test_annual_comparison_view_sums_months_and_separates_years(self):
        """Lista y PDF: una fila anual por cuenta, sin sumas de porcentajes."""
        Line = self.env['expense.budget.line']
        for month, planned, actual in [('1', 100, 50), ('2', 300, 75)]:
            line = Line.create({
                'budget_id': self.budget.id, 'account_id': self.account.id,
                'month': month, 'planned_amount': planned,
            })
            line.write({'actual_amount': actual})
        self.env.flush_all()
        Analysis = self.env['expense.budget.annual.analysis']
        row = Analysis.search([
            ('company_id', '=', self.company.id), ('year', '=', 2026),
            ('account_id', '=', self.account.id),
        ])
        self.assertEqual(len(row), 1)
        self.assertEqual(row.budget_id, self.budget)
        self.assertEqual(row.line_count, 2)
        self.assertEqual(row.planned_amount, 400)
        self.assertEqual(row.actual_amount, 125)
        self.assertEqual(row.variance_amount, 275)
        self.assertAlmostEqual(row.execution_percentage, 31.25)

        wizard = self.env['expense.budget.comparison.report.wizard'].create({
            'company_id': self.company.id, 'year': 2026,
        })
        report = self.env['report.expense_budget_control.report_comparison_document']
        result = report._prepare_comparison(wizard)
        self.assertEqual(result['account_count'], 1)
        self.assertEqual(result['line_count'], 2)
        self.assertEqual(result['grand_total']['planned'], 400)
        self.assertAlmostEqual(result['grand_total']['execution'], 31.25)

    def test_annual_comparison_approver_scope_excludes_drafts(self):
        """Las filas anuales del Aprobador excluyen datos de borradores."""
        Line = self.env['expense.budget.line']
        line = Line.create({
            'budget_id': self.budget.id, 'account_id': self.account.id,
            'month': '1', 'planned_amount': 80,
        })
        line.write({'actual_amount': 20})
        group = self.env.ref('expense_budget_control.group_expense_budget_approver')
        internal = self.env.ref('base.group_user')
        approver = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Aprobador anual controlado',
            'login': 'test_budget_approver_annual_1417',
            'company_id': self.company.id,
            'company_ids': [(6, 0, [self.company.id])],
            'groups_id': [(6, 0, [internal.id, group.id])],
        })
        self.env.flush_all()
        Analysis = self.env['expense.budget.annual.analysis'].with_user(approver)
        domain = [('company_id', '=', self.company.id),
                  ('year', '=', 2026), ('account_id', '=', self.account.id)]
        self.assertFalse(Analysis.search(domain))
        self.budget.action_submit()
        self.env.flush_all()
        rows = Analysis.search(domain)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows.scope, 'non_draft')
        self.assertEqual(rows.planned_amount, 80)

        # Una proyección del mismo año y cuenta en un presupuesto nuevo en
        # borrador NO debe incorporarse a los totales visibles para Aprobador.
        self.budget.action_approve()
        second = self.env['expense.budget'].create({
            'name': 'Presupuesto pendiente de registro',
            'company_id': self.company.id, 'year': 2026,
        })
        Line.create({
            'budget_id': second.id, 'account_id': self.account.id,
            'month': '4', 'planned_amount': 500,
        }).write({'actual_amount': 100})
        self.env.flush_all()
        rows = Analysis.search(domain)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows.planned_amount, 80)
        self.assertEqual(rows.actual_amount, 20)
        admin_rows = self.env['expense.budget.annual.analysis'].search(domain)
        self.assertEqual(len(admin_rows), 2)
        self.assertEqual(sum(admin_rows.mapped('planned_amount')), 580)
        self.assertEqual(sum(admin_rows.mapped('actual_amount')), 120)
        self.assertEqual(
            {row.budget_id.id for row in admin_rows}, {self.budget.id, second.id})

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

    def test_api_catalog_response_creates_categories_accounts_and_is_idempotent(self):
        sync = self.env['expense.budget.api.sync']
        payload = {'data': {
            'company_id': self.company.name,
            'Code': '101001', 'name': 'Servicio basico',
            'cuentas': [
                {'code': '101001', 'name': 'Agua'},
                {'code': '101002', 'name': 'Luz'},
                {'code': '101003', 'name': 'Internet'},
            ],
        }}
        kind, rows, parent_company = sync._extract_payload(payload)
        self.assertEqual(kind, 'catalog')
        first = sync._upsert_catalog(self.company, rows, parent_company)
        self.assertEqual(first['rubros_created'], 1)
        self.assertEqual(first['cuentas_created'], 3)

        Category = self.env['expense.budget.category']
        Account = self.env['expense.budget.account']
        rubro = Category.search([
            ('company_id', '=', self.company.id), ('code', '=', '101001'),
        ])
        self.assertEqual(rubro.name, 'Servicio basico')
        cuentas = Account.search([
            ('company_id', '=', self.company.id), ('category_id', '=', rubro.id),
        ])
        self.assertEqual({entry.name for entry in cuentas}, {'Agua', 'Luz', 'Internet'})
        self.assertEqual({entry.code for entry in cuentas}, {'101001', '101002', '101003'})

        again = sync._upsert_catalog(self.company, rows)
        self.assertEqual(again['rubros_created'], 0)
        self.assertEqual(again['rubros_unchanged'], 1)
        self.assertEqual(again['cuentas_unchanged'], 3)
        self.assertEqual(Account.search_count([
            ('company_id', '=', self.company.id), ('category_id', '=', rubro.id),
        ]), 3)

        rows[0]['cuentas'][0]['name'] = 'Agua potable'
        modified = sync._upsert_catalog(self.company, rows)
        self.assertEqual(modified['cuentas_updated'], 1)
        self.assertEqual(Account.search([
            ('company_id', '=', self.company.id), ('code', '=', '101001'),
        ]).name, 'Agua potable')

    def test_api_catalog_list_and_existing_expense_payload(self):
        sync = self.env['expense.budget.api.sync']
        catalog_response = {'data': [
            {'Code': 'R-1', 'name': 'Servicios', 'accounts': [
                {'code': 'A-1', 'name': 'Luz'}]},
            {'Code': 'R-2', 'name': 'Viajes', 'accounts': [
                {'code': 'A-2', 'name': 'Taxi'}]},
        ]}
        kind, rows, company_hint = sync._extract_payload(catalog_response)
        self.assertEqual(kind, 'catalog')
        self.assertFalse(company_hint)
        result = sync._upsert_catalog(self.company, rows)
        self.assertEqual(result['rubros_created'], 2)
        self.assertEqual(result['cuentas_created'], 2)
        self.assertEqual(self.env['expense.budget.account'].search_count([
            ('company_id', '=', self.company.id), ('code', 'in', ['A-1', 'A-2']),
        ]), 2)
        expense_rows = [{'id': 'G-01', 'codigo_cuenta': self.account.code,
                         'fecha': '2026-01-01', 'monto': 10, 'descripcion': 'Factura'}]
        kind, extracted, _hint = sync._extract_payload({'data': expense_rows})
        self.assertEqual(kind, 'expense')
        self.assertEqual(extracted, expense_rows)

    def test_api_catalog_does_not_import_into_wrong_company(self):
        sync = self.env['expense.budget.api.sync']
        payload = {'data': {'company_id': 'EMPRESA QUE NO COINCIDE',
                            'Code': 'R-X', 'name': 'No importar', 'cuentas': []}}
        kind, rows, parent_company = sync._extract_payload(payload)
        self.assertEqual(kind, 'catalog')
        with self.assertRaises(ValueError):
            sync._upsert_catalog(self.company, rows, parent_company)
        self.assertFalse(self.env['expense.budget.category'].search([
            ('company_id', '=', self.company.id), ('code', '=', 'R-X'),
        ]))

    def test_api_catalog_rejects_ambiguous_accounts(self):
        sync = self.env['expense.budget.api.sync']
        with self.assertRaises(ValueError):
            sync._upsert_catalog(self.company, [
                {'Code': 'R-A', 'name': 'A', 'cuentas': [
                    {'code': 'X', 'name': 'Cuenta de A'}]},
                {'Code': 'R-B', 'name': 'B', 'cuentas': [
                    {'code': 'X', 'name': 'Cuenta de B'}]},
            ])
