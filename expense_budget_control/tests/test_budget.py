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


    def test_create_category_from_budget_selector_with_unassigned_accounts(self):
        """Un registrador crea el rubro y elige cuentas ya existentes sin rubro."""
        base_group = self.env.ref('base.group_user')
        registrar_group = self.env.ref('expense_budget_control.group_expense_budget_registrar')
        registrar = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Registrador rubro y cuentas',
            'login': 'test_expense_budget_category_registrar_1420',
            'groups_id': [(6, 0, [base_group.id, registrar_group.id])],
            'company_id': self.company.id,
            'company_ids': [(6, 0, [self.company.id])],
        })
        available = self.env['expense.budget.account'].create({
            'code': 'AGUA-1420', 'name': 'Agua', 'company_id': self.company.id,
        })
        self.assertFalse(available.category_id)
        category = self.env['expense.budget.category'].with_user(registrar).create({
            'name': 'Servicios básicos de prueba',
            'company_id': self.company.id,
            'account_selection_ids': [(6, 0, [available.id])],
        })
        self.assertTrue(category.code.startswith('RUB-'))
        self.assertEqual(available.category_id, category)
        budget = self.env['expense.budget'].with_user(registrar).create({
            'category_id': category.id, 'year': 2042, 'company_id': self.company.id,
        })
        self.assertEqual(budget.name, category.name)
        line = self.env['expense.budget.line'].with_user(registrar).create({
            'budget_id': budget.id, 'account_id': available.id,
            'month': '1', 'planned_amount': 100,
        })
        self.assertEqual(line.account_id.category_id, category)
        # No convertir al registrador en administrador del catálogo.
        with self.assertRaises(AccessError):
            available.with_user(registrar).write({'name': 'Nombre modificado'})

    def test_category_can_select_multiple_existing_accounts_with_one_to_many(self):
        """El selector admite varias cuentas ya creadas, incluso con rubro previo.

        El vínculo se guarda en expense.budget.account.category_id.
        """
        extra = self.env['expense.budget.account'].create({
            'code': 'AGUA-1421', 'name': 'Agua', 'company_id': self.company.id,
        })
        category = self.env['expense.budget.category'].create({
            'name': 'Servicios básicos nuevos', 'company_id': self.company.id,
            'account_selection_ids': [(6, 0, [self.account.id, extra.id])],
        })
        self.assertEqual(self.account.category_id, category)
        self.assertEqual(extra.category_id, category)
        self.assertEqual(set(category.account_ids.ids), {self.account.id, extra.id})
        self.assertEqual(set(category.account_selection_ids.ids), {self.account.id, extra.id})
        # La vista ya no oculta las cuentas por tener rubro: el dominio es por empresa.
        from lxml import etree
        view = self.env.ref('expense_budget_control.view_expense_budget_category_form')
        arch = etree.fromstring(view.arch_db.encode())
        selector = arch.xpath("//field[@name='account_selection_ids']")[0]
        self.assertNotIn("('category_id', '=', False)", selector.get('domain'))

    def test_category_does_not_reassign_account_with_budget_movements(self):
        self.env['expense.budget.line'].create({
            'budget_id': self.budget.id, 'account_id': self.account.id,
            'month': '1', 'planned_amount': 200,
        })
        with self.assertRaises(ValidationError):
            self.env['expense.budget.category'].create({
                'name': 'Rubro nuevo', 'company_id': self.company.id,
                'account_selection_ids': [(6, 0, [self.account.id])],
            })
        self.assertEqual(self.account.category_id, self.category)

    def test_budget_lines_show_rubro_per_account_without_header_selector(self):
        """El rubro se muestra en cada línea, sin restringirse a la cabecera histórica."""
        from lxml import etree
        view = self.env.ref('expense_budget_control.view_expense_budget_form')
        arch = etree.fromstring(view.arch_db.encode())
        # No hay selector de rubro en la cabecera del presupuesto.
        self.assertFalse(arch.xpath("//form/sheet/group/group/field[@name='category_id']"))
        lines = arch.xpath("//field[@name='line_ids']/list")
        self.assertEqual(len(lines), 1)
        self.assertTrue(lines[0].xpath("./field[@name='category_id']"))
        self.assertNotIn('parent.category_id', lines[0].xpath("./field[@name='account_id']")[0].get('domain'))

        other = self.env['expense.budget.category'].create({
            'code': 'OTRO-RUBRO-1437', 'name': 'Otros gastos', 'company_id': self.company.id,
        })
        other_account = self.env['expense.budget.account'].create({
            'code': 'OTRA-CUENTA-1437', 'name': 'Alquiler',
            'category_id': other.id, 'company_id': self.company.id,
        })
        # Presupuesto creado previamente con un rubro en cabecera: las líneas
        # nuevas deben admitir cualquier cuenta de su empresa.
        budget = self.env['expense.budget'].create({
            'category_id': self.category.id, 'year': 2039, 'company_id': self.company.id,
        })
        line1 = self.env['expense.budget.line'].create({
            'budget_id': budget.id, 'account_id': self.account.id,
            'month': '1', 'planned_amount': 100,
        })
        line2 = self.env['expense.budget.line'].create({
            'budget_id': budget.id, 'account_id': other_account.id,
            'month': '2', 'planned_amount': 100,
        })
        self.assertEqual(line1.category_id, self.category)
        self.assertEqual(line2.category_id, other)
        with self.assertRaises(UserError):
            budget.write({'category_id': other.id})

    def test_comparison_pdf_execution_matches_grouped_view(self):
        """10% + 0% en Odoo debe imprimir 10%, no la razón global 6,67%."""
        water = self.env['expense.budget.account'].create({
            'code': 'AGUA-TEST-1419', 'name': 'Agua',
            'category_id': self.category.id, 'company_id': self.company.id,
        })
        self.env['expense.budget.line'].create({
            'budget_id': self.budget.id, 'account_id': self.account.id,
            'month': '1', 'planned_amount': 50,
        })
        line = self.env['expense.budget.line'].create({
            'budget_id': self.budget.id, 'account_id': water.id,
            'month': '1', 'planned_amount': 100,
        })
        line.write({'actual_amount': 10})
        wizard = self.env['expense.budget.comparison.report.wizard'].create({
            'company_id': self.company.id, 'year': 2026,
            'category_id': self.category.id,
            'month_ids': [(6, 0, self.env['expense.budget.comparison.month'].search([('number', '=', 1)]).ids)],
        })
        data = self.env['report.expense_budget_control.report_comparison_document']._prepare_comparison(wizard)
        self.assertEqual(data['grand_total']['planned'], 150)
        self.assertEqual(data['grand_total']['actual'], 10)
        self.assertAlmostEqual(data['grand_total']['execution'], 10)
        self.assertTrue(data['summary_by_category_only'])

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
            ['draft', 'to_approve', 'approved', 'rejected'],
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
        self.assertEqual(states, ['draft', 'to_approve', 'approved', 'rejected'])

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

    def test_comparison_no_account_filter_lists_every_budgeted_account(self):
        """Con cuentas vacías incluir cuentas presupuestadas de todos los rubros.

        El filtro opcional de rubro y la selección explícita deben conservarse.
        Las cuentas del catálogo que no tienen proyecciones no se imprimen.
        """
        Account = self.env['expense.budget.account']
        Category = self.env['expense.budget.category']
        Line = self.env['expense.budget.line']
        water = Account.create({
            'code': 'PDF-AUTO-WATER', 'name': 'Agua',
            'category_id': self.category.id, 'company_id': self.company.id,
        })
        unbudgeted = Account.create({
            'code': 'PDF-AUTO-NO-BUDGET', 'name': 'Internet',
            'category_id': self.category.id, 'company_id': self.company.id,
        })
        other_category = Category.create({
            'code': 'PDF-AUTO-OTHER', 'name': 'Transporte',
            'company_id': self.company.id,
        })
        travel = Account.create({
            'code': 'PDF-AUTO-TRAVEL', 'name': 'Pasajes',
            'category_id': other_category.id, 'company_id': self.company.id,
        })
        for account, month, planned in (
                (self.account, '1', 100),
                (water, '2', 200),
                (travel, '3', 300)):
            Line.create({
                'budget_id': self.budget.id,
                'account_id': account.id,
                'month': month,
                'planned_amount': planned,
            })
        Report = self.env['report.expense_budget_control.report_comparison_document']
        Wizard = self.env['expense.budget.comparison.report.wizard']
        wizard = Wizard.create({
            'company_id': self.company.id, 'year': '2026',
        })
        self.assertFalse(wizard.account_ids)
        result = Report._prepare_comparison(wizard)
        account_ids = {
            account['account'].id
            for group in result['categories'] for account in group['accounts']
        }
        self.assertEqual(account_ids, {self.account.id, water.id, travel.id})
        self.assertNotIn(unbudgeted.id, account_ids)
        self.assertEqual(result['line_count'], 3)
        self.assertEqual(result['grand_total']['planned'], 600)
        self.assertEqual([m['number'] for m in result['pages'][0]['months']],
                         list(range(1, 13)))

        # Rubro sin seleccionar cuentas: todas las cuentas presupuestadas del rubro.
        wizard.category_id = self.category
        filtered = Report._prepare_comparison(wizard)
        ids_with_category = {
            account['account'].id
            for group in filtered['categories'] for account in group['accounts']
        }
        self.assertEqual(ids_with_category, {self.account.id, water.id})
        self.assertEqual(filtered['grand_total']['planned'], 300)

        # Una cuenta elegida expresamente sí limita el PDF.
        wizard.account_ids = [(6, 0, [water.id])]
        only_water = Report._prepare_comparison(wizard)
        self.assertEqual(only_water['line_count'], 1)
        self.assertEqual(only_water['grand_total']['planned'], 200)

    def test_comparison_pdf_groups_accounts_and_matches_view_execution(self):
        """El PDF debe sumar Ejecución (%) igual que la vista agrupada de Odoo."""
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
            'month_ids': [(6, 0, self.env['expense.budget.comparison.month'].search([]).ids)],
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
        self.assertAlmostEqual(prepared['grand_total']['execution'], 75.0)
        self.assertEqual(wizard.action_print_pdf()['type'], 'ir.actions.report')

        filtered = self.env['expense.budget.comparison.report.wizard'].create({
            'company_id': self.company.id, 'year': 2026,
            'category_id': self.category.id, 'account_id': water.id,
            'month_ids': [(6, 0, self.env['expense.budget.comparison.month'].search([]).ids)],
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
            'month_ids': [(6, 0, self.env['expense.budget.comparison.month'].search([]).ids)],
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
        self.assertAlmostEqual(result['grand_total']['execution'], 40 + 10 + 40 + 0 + 30 / 70 * 100)
        self.assertEqual(
            {detail['line'].budget_id.id for acc in group['accounts']
             for detail in acc['lines']},
            {self.budget.id, second.id},
        )

        # Cambiar el rubro no puede conservar el filtro por una cuenta anterior.
        wizard.account_id = agua
        wizard._onchange_category_id()
        self.assertFalse(wizard.account_id)
        self.assertEqual(report._prepare_comparison(wizard)['line_count'], 5)

        # Solo cuando se escoge explícitamente Cuenta se limita el reporte.
        wizard.account_id = agua
        self.assertEqual(report._prepare_comparison(wizard)['line_count'], 2)

    def test_comparison_rubro_excludes_unbudgeted_accounts_and_names_in_pdf(self):
        """Sin filtro de cuenta, incluir solo las que tienen presupuesto en el año."""
        from lxml import etree

        water = self.env['expense.budget.account'].create({
            'code': 'AGUA-SIN-MOV-1439', 'name': 'Agua',
            'company_id': self.company.id, 'category_id': self.category.id,
        })
        self.env['expense.budget.line'].create({
            'budget_id': self.budget.id, 'account_id': self.account.id,
            'month': '1', 'planned_amount': 150,
        })
        wizard = self.env['expense.budget.comparison.report.wizard'].create({
            'company_id': self.company.id, 'year': 2026,
            'category_id': self.category.id,
        })
        result = self.env[
            'report.expense_budget_control.report_comparison_document'
        ]._prepare_comparison(wizard)
        self.assertEqual(result['line_count'], 1)
        self.assertEqual(result['grand_total']['planned'], 150)
        accounts = result['categories'][0]['accounts']
        self.assertEqual({r['account'].id for r in accounts}, {self.account.id})
        self.assertNotIn(water.id, [entry['account'].id for entry in accounts])

        template = self.env.ref('expense_budget_control.report_comparison_document')
        arch = etree.fromstring(template.arch_db.encode('utf-8'))
        # El detalle no se omite cuando solo se selecciona el rubro.
        self.assertFalse(arch.xpath("//*[contains(@t-if, 'summary_by_category_only')]"))
        # Las filas de presupuestos muestran el nombre de su cuenta, no el name
        # del presupuesto (por ejemplo, Luz en vez de Presupuesto Enero).
        budget_names = arch.xpath("""//*[@t-set='row_name' and @t-value="account['account'].name"]""")
        self.assertEqual(len(budget_names), 1)

    def test_comparison_pdf_multiple_accounts_and_category_summary(self):
        """Varias cuentas activan el detalle; solo rubro imprime sus totales."""
        Account = self.env['expense.budget.account']
        Line = self.env['expense.budget.line']
        water = Account.create({
            'code': 'MULTI-AGUA', 'name': 'Agua',
            'company_id': self.company.id, 'category_id': self.category.id,
        })
        internet = Account.create({
            'code': 'MULTI-INTERNET', 'name': 'Internet',
            'company_id': self.company.id, 'category_id': self.category.id,
        })
        for account, month, planned, actual in (
                (self.account, '1', 100, 40),
                (water, '2', 200, 50),
                (internet, '3', 300, 90)):
            line = Line.create({
                'budget_id': self.budget.id, 'account_id': account.id,
                'month': month, 'planned_amount': planned,
            })
            line.write({'actual_amount': actual})

        wizard_model = self.env['expense.budget.comparison.report.wizard']
        report = self.env['report.expense_budget_control.report_comparison_document']
        summary_wizard = wizard_model.create({
            'company_id': self.company.id, 'year': 2026,
            'category_id': self.category.id,
        })
        summary = report._prepare_comparison(summary_wizard)
        self.assertTrue(summary['summary_by_category_only'])
        self.assertEqual(summary['line_count'], 3)
        self.assertEqual(summary['grand_total']['planned'], 600)
        self.assertEqual(summary['grand_total']['actual'], 180)
        self.assertEqual(summary['grand_total']['available'], 420)
        self.assertAlmostEqual(summary['grand_total']['execution'], 95)

        multi_wizard = wizard_model.create({
            'company_id': self.company.id, 'year': 2026,
            'category_id': self.category.id,
            'account_ids': [(6, 0, [self.account.id, water.id])],
        })
        selected = report._prepare_comparison(multi_wizard)
        self.assertFalse(selected['summary_by_category_only'])
        self.assertEqual(selected['line_count'], 2)
        self.assertEqual(selected['grand_total']['planned'], 300)
        self.assertEqual(selected['grand_total']['actual'], 90)
        self.assertEqual(
            {item['account'].id for item in selected['categories'][0]['accounts']},
            {self.account.id, water.id},
        )
        self.assertEqual(
            sum(len(account['lines']) for account in selected['categories'][0]['accounts']),
            2,
        )
        multi_wizard._onchange_category_id()
        self.assertFalse(multi_wizard.account_ids)

    def test_comparison_year_not_summed_in_grouped_view(self):
        """El año agrupado debe ser 2026, no 2026 + 2026."""
        self.assertEqual(self.env['expense.budget.line']._fields['year'].aggregator, 'max')

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
            'month_ids': [(6, 0, self.env['expense.budget.comparison.month'].search([]).ids)],
        })
        report = self.env['report.expense_budget_control.report_comparison_document'].with_user(approver)
        self.assertEqual(report._prepare_comparison(wizard)['line_count'], 0)
        self.budget.action_submit()
        self.assertEqual(report._prepare_comparison(wizard)['line_count'], 1)


    def test_report_months_start_unselected(self):
        """El usuario elige los meses; no se precargan los doce."""
        wizard = self.env['expense.budget.comparison.report.wizard'].create({
            'company_id': self.company.id,
            'year': 2026,
        })
        self.assertFalse(wizard.month_ids)
        action = wizard.action_print_pdf()
        self.assertEqual(action['report_name'], 'expense_budget_control.report_comparison_document')
        result = self.env['report.expense_budget_control.report_comparison_document']._prepare_comparison(wizard)
        self.assertEqual([m['number'] for m in result['pages'][0]['months']], list(range(1, 13)))
        self.assertFalse(wizard.month_ids)

    def test_monthly_comparison_with_selected_nonconsecutive_months(self):
        """Febrero/Abril: disponible inicial enero más disponibles seleccionados."""
        Line = self.env['expense.budget.line']
        for month, planned, actual in (
                ('1', 100, 30), ('2', 200, 50), ('3', 300, 80), ('4', 400, 120)):
            line = Line.create({
                'budget_id': self.budget.id,
                'account_id': self.account.id,
                'month': month,
                'planned_amount': planned,
            })
            line.write({'actual_amount': actual})
        months = self.env['expense.budget.comparison.month'].search([('number', 'in', [2, 4])])
        wizard = self.env['expense.budget.comparison.report.wizard'].create({
            'year': 2026, 'company_id': self.company.id,
            'category_id': self.category.id,
            'month_ids': [(6, 0, months.ids)],
        })
        report = self.env['report.expense_budget_control.report_comparison_document']
        data = report._prepare_comparison(wizard)
        self.assertEqual([month['number'] for month in data['pages'][0]['months']], [2, 4])
        group = data['categories'][0]
        self.assertTrue(data['summary_by_category_only'])
        self.assertAlmostEqual(group['monthly_report']['openings'][2], 70)
        feb = group['monthly_report']['cells'][2]
        self.assertAlmostEqual(feb['planned'], 200)
        self.assertAlmostEqual(feb['actual'], 50)
        self.assertAlmostEqual(feb['available'], 150)
        april = group['monthly_report']['cells'][4]
        self.assertAlmostEqual(april['planned'], 400)
        self.assertAlmostEqual(april['actual'], 120)
        self.assertAlmostEqual(april['available'], 280)
        self.assertAlmostEqual(group['monthly_report']['openings'][4], 220)
        # Marzo no seleccionado no suma a Saldo actual (50 + 120).
        closing = group['monthly_report']['period_closings'][2]
        self.assertAlmostEqual(closing['saldo_actual'], 170)
        self.assertAlmostEqual(closing['saldo_disponible'], 500)

    def test_comparison_pdf_balance_follows_previous_period_and_selected_months(self):
        """En marzo, inicial disponible de febrero más disponibles marzo/abril."""
        Line = self.env['expense.budget.line']
        for month, planned, actual in (
                ('1', 500, 100), ('2', 200, 50),
                ('3', 150, 60), ('4', 250, 80), ('5', 300, 90)):
            line = Line.create({
                'budget_id': self.budget.id, 'account_id': self.account.id,
                'month': month, 'planned_amount': planned,
            })
            line.write({'actual_amount': actual})
        months = self.env['expense.budget.comparison.month'].search([
            ('number', 'in', [3, 4]),
        ])
        wizard = self.env['expense.budget.comparison.report.wizard'].create({
            'year': 2026, 'company_id': self.company.id,
            'category_id': self.category.id,
            'month_ids': [(6, 0, months.ids)],
        })
        report = self.env['report.expense_budget_control.report_comparison_document']
        group = report._prepare_comparison(wizard)['categories'][0]
        self.assertAlmostEqual(group['monthly_report']['openings'][3], 150)
        closing = group['monthly_report']['period_closings'][3]
        self.assertAlmostEqual(closing['saldo_actual'], 140)
        self.assertAlmostEqual(closing['saldo_disponible'], 410)

    def test_comparison_pdf_balance_all_selected_months_in_one_row(self):
        """Todos los meses elegidos se imprimen juntos y con un saldo único."""
        Line = self.env['expense.budget.line']
        for month in range(1, 7):
            line = Line.create({
                'budget_id': self.budget.id, 'account_id': self.account.id,
                'month': str(month), 'planned_amount': 100,
            })
            line.write({'actual_amount': 10})
        months = self.env['expense.budget.comparison.month'].search([
            ('number', 'in', [2, 3, 4, 5]),
        ])
        wizard = self.env['expense.budget.comparison.report.wizard'].create({
            'year': 2026, 'company_id': self.company.id,
            'category_id': self.category.id,
            'month_ids': [(6, 0, months.ids)],
        })
        report = self.env['report.expense_budget_control.report_comparison_document']
        data = report._prepare_comparison(wizard)
        self.assertEqual(len(data['pages']), 1)
        self.assertEqual([month['number'] for month in data['pages'][0]['months']], [2, 3, 4, 5])
        row = data['categories'][0]['monthly_report']
        self.assertAlmostEqual(row['openings'][2], 90)
        self.assertAlmostEqual(row['period_closings'][2]['saldo_actual'], 40)
        self.assertAlmostEqual(row['period_closings'][2]['saldo_disponible'], 450)

    def test_comparison_initial_uses_previous_available_and_adds_selected_available(self):
        """Saldo inicial = disponible enero; restante = inicial + disponibles febrero/marzo."""
        Line = self.env['expense.budget.line']
        for month, planned, actual in (
                ('1', 500, 450), ('2', 300, 200), ('3', 200, 150)):
            line = Line.create({
                'budget_id': self.budget.id, 'account_id': self.account.id,
                'month': month, 'planned_amount': planned,
            })
            line.write({'actual_amount': actual})
        months = self.env['expense.budget.comparison.month'].search([
            ('number', 'in', [2, 3]),
        ])
        wizard = self.env['expense.budget.comparison.report.wizard'].create({
            'year': 2026, 'company_id': self.company.id,
            'category_id': self.category.id,
            'month_ids': [(6, 0, months.ids)],
        })
        result = self.env['report.expense_budget_control.report_comparison_document']._prepare_comparison(wizard)
        report_data = result['grand_row']['monthly_report']
        self.assertAlmostEqual(report_data['openings'][2], 50)
        self.assertAlmostEqual(report_data['period_closings'][2]['saldo_actual'], 350)
        self.assertAlmostEqual(report_data['period_closings'][2]['saldo_disponible'], 200)

    def test_comparison_saldo_inicial_150_febrero_140_marzo_120(self):
        """150 disponible de enero + 140 de febrero + 120 de marzo = 410."""
        report = self.env['report.expense_budget_control.report_comparison_document']
        row = {'monthly': report._empty_months()}
        row['monthly'][1].update({'planned': 250, 'actual': 100, 'available': 150})
        row['monthly'][2].update({'planned': 200, 'actual': 60, 'available': 140})
        row['monthly'][3].update({'planned': 170, 'actual': 50, 'available': 120})
        report._finish_row(row, [2, 3])
        monthly = row['monthly_report']
        self.assertEqual(monthly['openings'][2], 150)
        self.assertEqual(monthly['period_closings'][2]['saldo_actual'], 110)
        self.assertEqual(monthly['period_closings'][2]['saldo_disponible'], 410)

    def test_rejection_is_only_possible_for_approver_while_pending(self):
        group = self.env.ref('expense_budget_control.group_expense_budget_approver')
        registrar_group = self.env.ref('expense_budget_control.group_expense_budget_registrar')
        base_group = self.env.ref('base.group_user')
        approver = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Aprobador rechazos prueba',
            'login': 'test_approver_reject_1423',
            'company_id': self.company.id,
            'company_ids': [(6, 0, [self.company.id])],
            'groups_id': [(6, 0, [base_group.id, group.id])],
        })
        registrar = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Registrador rechazos prueba',
            'login': 'test_registrar_reject_1423',
            'company_id': self.company.id,
            'company_ids': [(6, 0, [self.company.id])],
            'groups_id': [(6, 0, [base_group.id, registrar_group.id])],
        })
        self.env['expense.budget.line'].create({
            'budget_id': self.budget.id, 'account_id': self.account.id,
            'month': '1', 'planned_amount': 100,
        })
        with self.assertRaises(AccessError):
            self.budget.with_user(registrar).action_reject()
        self.budget.action_submit()
        self.budget.with_user(approver).action_reject()
        self.assertEqual(self.budget.state, 'rejected')
        self.assertIn(self.budget.id, self.env['expense.budget'].with_user(approver).search([]).ids)
        with self.assertRaises(UserError):
            self.budget.with_user(approver).action_reject()
        with self.assertRaises(UserError):
            self.budget.with_user(approver).action_approve()


@tagged('post_install', '-at_install')
class TestExpenseBudgetReportPeriod(TransactionCase):
    def setUp(self):
        super().setUp()
        self.company = self.env.company
        self.category = self.env['expense.budget.category'].create({
            'code': 'PERIODO-TEST', 'name': 'Servicios de prueba', 'company_id': self.company.id,
        })
        self.account = self.env['expense.budget.account'].create({
            'code': 'PERIODO-CTA', 'name': 'Luz', 'company_id': self.company.id,
            'category_id': self.category.id,
        })
        self.budget = self.env['expense.budget'].create({
            'name': 'Presupuesto de prueba por períodos',
            'company_id': self.company.id, 'year': 2049,
        })
        self.env['expense.budget.line'].create({
            'budget_id': self.budget.id, 'account_id': self.account.id,
            'month': '2', 'planned_amount': 200, 'actual_amount': 50,
        })

    def test_annual_report_restored_to_budget(self):
        action = self.budget.action_print_annual_pdf()
        self.assertEqual(action['report_name'],
                         'expense_budget_control.report_annual_budget_document')
        values = self.env[
            'report.expense_budget_control.report_annual_budget_document'
        ]._get_report_values([self.budget.id])
        report = values['reports'][0]
        self.assertEqual(report['annual_total']['planned'], 200)
        self.assertEqual(report['annual_total']['actual'], 50)
        self.assertEqual(report['annual_total']['available'], 150)

    def test_monthly_report_empty_months_prints_all_twelve(self):
        wizard = self.env['expense.budget.comparison.report.wizard'].create({
            'company_id': self.company.id, 'year': '2049',
        })
        self.assertFalse(wizard.month_ids)
        action = wizard.action_print_pdf()
        self.assertEqual(action['report_name'],
                         'expense_budget_control.report_comparison_document')
        report = self.env['report.expense_budget_control.report_comparison_document']._prepare_comparison(wizard)
        self.assertEqual([m['number'] for m in report['pages'][0]['months']], list(range(1, 13)))
        self.assertFalse(wizard.month_ids)
        group = report['categories'][0]
        self.assertEqual(group['monthly_report']['cells'][2]['planned'], 200)
        self.assertEqual(group['monthly_report']['cells'][2]['actual'], 50)
        self.assertEqual(group['monthly_report']['cells'][2]['available'], 150)
        self.assertEqual(group['monthly_report']['period_closings'][1]['saldo_actual'], 50)
        self.assertEqual(group['monthly_report']['period_closings'][1]['saldo_disponible'], 150)

    def test_monthly_report_selected_month_only(self):
        wizard = self.env['expense.budget.comparison.report.wizard'].create({
            'company_id': self.company.id, 'year': '2049',
        })
        month = self.env['expense.budget.comparison.month'].search([('number', '=', 2)], limit=1)
        self.assertTrue(month)
        wizard.month_ids = [(6, 0, month.ids)]
        action = wizard.action_print_pdf()
        self.assertEqual(action['report_name'],
                         'expense_budget_control.report_comparison_document')
        report = self.env['report.expense_budget_control.report_comparison_document']._prepare_comparison(wizard)
        self.assertEqual([m['number'] for m in report['pages'][0]['months']], [2])

    def test_budget_consumed_readonly_in_form_lines(self):
        """En presupuestos, las proyecciones no dejan editar Consumido."""
        from lxml import etree
        view = self.env.ref('expense_budget_control.view_expense_budget_form')
        arch = etree.fromstring(view.arch_db.encode())
        fields = arch.xpath("//field[@name='line_ids']/list/field[@name='actual_amount']")
        self.assertEqual(len(fields), 1)
        self.assertIn(fields[0].get('readonly'), ('1', 'True'))

    def test_comparison_rubro_includes_budget_values_in_total_general(self):
        """Un rubro seleccionado no debe perder sus líneas ni sus importes."""
        wizard = self.env['expense.budget.comparison.report.wizard'].create({
            'company_id': self.company.id, 'year': '2049',
            'category_id': self.category.id,
        })
        data = self.env['report.expense_budget_control.report_comparison_document']._prepare_comparison(wizard)
        self.assertTrue(data['summary_by_category_only'])
        self.assertEqual(data['line_count'], 1)
        self.assertEqual(len(data['categories']), 1)
        self.assertEqual(data['categories'][0]['category'], self.category)
        self.assertEqual(data['grand_total']['planned'], 200)
        self.assertEqual(data['grand_total']['actual'], 50)
        self.assertEqual(data['grand_total']['available'], 150)
        grand = data['grand_row']['monthly_report']
        self.assertEqual(grand['cells'][2]['planned'], 200)
        self.assertEqual(grand['cells'][2]['actual'], 50)
        self.assertEqual(grand['cells'][2]['available'], 150)
        self.assertEqual(grand['period_closings'][1]['saldo_disponible'], 150)

