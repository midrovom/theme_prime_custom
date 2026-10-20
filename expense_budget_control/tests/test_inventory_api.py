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

    def test_nested_payload_and_optional_endpoint_query(self):
        from types import SimpleNamespace
        rows = self.sync._rows({'data': {'items': [
            {'Codigo': '601010101002', 'Nombre': 'Decimo Tercer Sueldo'},
        ]}})
        self.assertEqual(len(rows), 1)
        self.assertTrue(self.sync._matches_endpoint(SimpleNamespace(
            end_point='https://example.invalid/inventory_odoo/consulta_odoo/getconsumosgastos/2?x=1',
        ), 'consumptions'))

    def test_subcenter_year_month_center_and_consumed(self):
        """La proyección 2022 ADM/GDE recibe 161.82; otros años/centros no."""
        account = self.account_model.create({
            'company_id': self.company.id, 'code': '601010101002',
            'name': 'Decimo Tercer Sueldo',
        })
        center = self.center_model.create({
            'company_id': self.company.id, 'code': 'ADM', 'name': 'Administración',
        })
        budget_2022 = self.env['expense.budget'].create({
            'company_id': self.company.id, 'name': 'Personal 2022', 'year': 2022,
        })
        budget_2026 = self.env['expense.budget'].create({
            'company_id': self.company.id, 'name': 'Personal 2026', 'year': 2026,
        })
        line_model = self.env['expense.budget.line']
        line_2022 = line_model.create({
            'budget_id': budget_2022.id, 'account_id': account.id,
            'cost_center_id': center.id, 'subcenter_code': 'GDE',
            'month': '7', 'planned_amount': 200,
        })
        line_2026 = line_model.create({
            'budget_id': budget_2026.id, 'account_id': account.id,
            'cost_center_id': center.id, 'subcenter_code': 'GDE',
            'month': '7', 'planned_amount': 300,
        })
        expense_model = self.env['expense.budget.expense']
        expense = expense_model.create({
            'company_id': self.company.id, 'account_id': account.id,
            'cost_center_id': center.id, 'subcenter_code': 'GDE',
            'date': '2022-07-25', 'amount': 161.82,
            'description': 'Consumo API de prueba',
        })
        self.assertEqual(expense.budget_line_id, line_2022)
        self.assertAlmostEqual(line_2022.actual_amount, 161.82)
        self.assertAlmostEqual(line_2026.actual_amount, 0.0)
        self.assertFalse(expense_model._find_budget_line(
            self.company.id, account.id, '2022-07-25', False, 'GDE'))

    def test_subcenter_no_longer_splits_line_and_duplicates_blocked(self):
        account = self.account_model.create({
            'company_id': self.company.id, 'code': '601010101099',
            'name': 'Servicios para subcentros',
        })
        center = self.center_model.create({
            'company_id': self.company.id, 'code': 'ADM-TEST-SUB', 'name': 'Administración',
        })
        budget = self.env['expense.budget'].create({
            'company_id': self.company.id, 'name': 'Prueba subcentros', 'year': 2091,
        })
        Line = self.env['expense.budget.line']
        generic = Line.create({
            'budget_id': budget.id, 'account_id': account.id,
            'cost_center_id': center.id, 'month': '6', 'planned_amount': 200,
        })
        Expense = self.env['expense.budget.expense']
        first = Expense.create({
            'company_id': self.company.id, 'account_id': account.id,
            'cost_center_id': center.id, 'subcenter_code': 'GDE',
            'date': '2091-06-15', 'amount': 40, 'description': 'Antes de especificar',
        })
        self.assertEqual(first.budget_line_id, generic)
        with self.assertRaises(ValidationError):
            with self.env.cr.savepoint():
                Line.create({
                    'budget_id': budget.id, 'account_id': account.id,
                    'cost_center_id': center.id, 'subcenter_code': 'GDE',
                    'month': '6', 'planned_amount': 120,
                })
        second = Expense.create({
            'company_id': self.company.id, 'account_id': account.id,
            'cost_center_id': center.id, 'subcenter_code': 'OTRO',
            'date': '2091-06-17', 'amount': 30, 'description': 'Otro subcentro',
        })
        self.assertEqual(second.budget_line_id, generic)
        self.assertAlmostEqual(generic.actual_amount, 70)

    def test_imported_consumed_relinked_when_rubro_and_line_created_later(self):
        """ERP primero; después rubro/cuenta/centro/subcentro/año/mes."""
        self.sync._sync_accounts(self.company, [
            {'Codigo': '601010101002', 'Nombre': 'Decimo Tercer Sueldo'},
        ])
        self.sync._sync_centers(self.company, [
            {'Codigo': 'ADM    ', 'Nombre': 'Administración'},
        ])
        account = self.account_model.search([
            ('company_id', '=', self.company.id), ('code', '=', '601010101002'),
        ], limit=1)
        center = self.center_model.search([
            ('company_id', '=', self.company.id), ('code', '=', 'ADM'),
        ], limit=1)
        # El consumo fue importado ANTES de crear el rubro / la proyección.
        expense = self.env['expense.budget.expense'].create({
            'company_id': self.company.id, 'account_id': account.id,
            'cost_center_id': center.id, 'subcenter_code': ' gde   ',
            'date': '2022-07-25', 'amount': 161.82,
            'description': 'getconsumosgastos/2',
        })
        self.assertEqual(expense.subcenter_code, 'GDE')
        self.assertFalse(expense.budget_line_id)
        category = self.env['expense.budget.category'].create({
            'company_id': self.company.id, 'name': 'Gastos de personal prueba',
        })
        category.write({'account_selection_ids': [(6, 0, [account.id])]})
        self.assertEqual(account.category_id, category)
        budget = self.env['expense.budget'].create({
            'company_id': self.company.id, 'name': 'Año del consumo 2022',
            'year': 2022,
        })
        line = self.env['expense.budget.line'].create({
            'budget_id': budget.id, 'account_id': account.id,
            'cost_center_id': center.id, 'subcenter_code': ' gde ',
            'month': '7', 'planned_amount': 500,
        })
        self.assertEqual(line.subcenter_code, 'GDE')
        self.assertEqual(expense.budget_line_id, line)
        self.assertAlmostEqual(line.actual_amount, 161.82)
        self.assertEqual(category.cost_center_ids, center)
        # Aunque varíe Subcentro, la misma cuenta+centro+mes no se duplica.
        with self.assertRaises(ValidationError):
            with self.env.cr.savepoint():
                self.env['expense.budget.line'].create({
                    'budget_id': budget.id, 'account_id': account.id,
                    'cost_center_id': center.id, 'subcenter_code': 'OTRO',
                    'month': '7', 'planned_amount': 100,
                })

    def test_existing_catalogs_with_inactive_or_historical_padded_codes(self):
        """Una API no debe insertar un código si ya existe (inactivo o con espacios)."""
        account = self.account_model.create({
            'company_id': self.company.id, 'code': '601010109991',
            'name': 'Nombre anterior', 'active': False,
        })
        center = self.center_model.create({
            'company_id': self.company.id, 'code': 'MAT-LEG',
            'name': 'Nombre anterior', 'active': False,
        })
        # Representa registros antiguos cuyo código no se normalizaba.
        self.env.cr.execute(
            'UPDATE expense_budget_account SET code = %s WHERE id = %s',
            (' 601010109991  ', account.id),
        )
        self.env.cr.execute(
            'UPDATE expense_budget_cost_center SET code = %s WHERE id = %s',
            ('MAT-LEG       ', center.id),
        )
        self.env.invalidate_all()
        result_accounts = self.sync._sync_accounts(self.company, [
            {'Codigo': '601010109991', 'Nombre': 'Sueldos y Salarios'},
        ])
        result_centers = self.sync._sync_centers(self.company, [
            {'Codigo': 'MAT-LEG', 'Nombre': 'Centro actualizado'},
        ])
        self.assertEqual(result_accounts['created'], 0)
        self.assertEqual(result_accounts['updated'], 1)
        self.assertEqual(result_centers['created'], 0)
        self.assertEqual(result_centers['updated'], 1)
        self.assertEqual(account.code, '601010109991')
        self.assertEqual(center.code, 'MAT-LEG')
        self.assertTrue(account.active)
        self.assertTrue(center.active)
        self.assertEqual(account.name, 'Sueldos y Salarios')
        self.assertEqual(center.name, 'Centro actualizado')
        self.assertEqual(self.account_model.with_context(active_test=False).search_count([
            ('company_id', '=', self.company.id), ('code', '=', '601010109991'),
        ]), 1)
        self.assertEqual(self.center_model.with_context(active_test=False).search_count([
            ('company_id', '=', self.company.id), ('code', '=', 'MAT-LEG'),
        ]), 1)

    def test_consumptions_reuse_existing_catalogs_not_create_placeholders(self):
        """Cuando ambos catálogos ya existen, consumos no debe intentar insertarlos."""
        account = self.account_model.create({
            'company_id': self.company.id, 'code': '601010109992',
            'name': 'Décimo tercer sueldo',
        })
        center = self.center_model.create({
            'company_id': self.company.id, 'code': 'ADM-992',
            'name': 'Administración',
        })
        budget = self.env['expense.budget'].create({
            'company_id': self.company.id, 'name': 'Regresión duplicados 2022',
            'year': 2022,
        })
        line = self.env['expense.budget.line'].create({
            'budget_id': budget.id, 'account_id': account.id,
            'cost_center_id': center.id, 'subcenter_code': 'GDE',
            'month': '7', 'planned_amount': 300,
        })
        api_record = self.env['api.administrator'].sudo().search([
            ('company_id', '=', self.company.id),
        ], limit=1)
        if not api_record:
            self.skipTest('Se necesita una conexión api.administrator de prueba.')
        rows = [{
            'Codigo': '601010109992', 'Valor': '161.82',
            'Fecha': 'jul 25 2022 12:00:00:000',
            'Centro': 'ADM-992       ', 'Subcentro': 'GDE       ',
        }]
        first = self.sync._sync_consumptions(self.company, rows, api_record, 2022)
        second = self.sync._sync_consumptions(self.company, rows, api_record, 2022)
        self.assertEqual(first['placeholder_accounts'], 0)
        self.assertEqual(first['placeholder_centers'], 0)
        self.assertEqual(first['created'], 1)
        self.assertEqual(second['created'], 0)
        self.assertEqual(second['unchanged'], 1)
        self.assertAlmostEqual(line.actual_amount, 161.82)
        self.assertEqual(self.account_model.search_count([
            ('company_id', '=', self.company.id), ('code', '=', '601010109992'),
        ]), 1)
        self.assertEqual(self.center_model.search_count([
            ('company_id', '=', self.company.id), ('code', '=', 'ADM-992'),
        ]), 1)

    def test_guardar_proyeccion_consulta_codigo_centro_subcentro_mes_anio(self):
        """El ERP puede devolver muchos años: solo cargar abril 2020/DIC/GDE."""
        Account = self.account_model.with_context(active_test=False)
        Center = self.center_model.with_context(active_test=False)
        account = Account.create({
            'company_id': self.company.id, 'code': '601010101002-TEST-2020',
            'name': 'Décimo Tercer Sueldo prueba',
        })
        center = Center.create({
            'company_id': self.company.id, 'code': 'DIC-TEST-2020',
            'name': 'Centro DIC prueba',
        })
        opts = {'skip_expense_budget_consumption_on_save': True}
        budget = self.env['expense.budget'].with_context(**opts).create({
            'company_id': self.company.id, 'name': 'Presupuesto ejemplo abril', 'year': 2020,
        })
        line = self.env['expense.budget.line'].with_context(**opts).create({
            'budget_id': budget.id, 'account_id': account.id,
            'cost_center_id': center.id, 'subcenter_code': 'GDE',
            'month': '4', 'planned_amount': 100,
        })
        rows = [
            {'Codigo': account.code, 'Centro': 'DIC-TEST-2020   ', 'Subcentro': 'GDE   ',
             'Fecha': 'abr 25 2020 12:00:00:000', 'Valor': '50.00'},
            {'Codigo': account.code, 'Centro': 'DIC-TEST-2020', 'Subcentro': 'GDE',
             'Fecha': 'abr 26 2020 12:00:00:000', 'Valor': '10.00'},
            {'Codigo': account.code, 'Centro': 'DIC-TEST-2020', 'Subcentro': 'GDE',
             'Fecha': 'jul 25 2020 12:00:00:000', 'Valor': '999.00'},
            {'Codigo': account.code, 'Centro': 'DIC-TEST-2020', 'Subcentro': 'GDE',
             'Fecha': 'abr 25 2026 12:00:00:000', 'Valor': '999.00'},
            {'Codigo': account.code, 'Centro': 'ADM', 'Subcentro': 'GDE',
             'Fecha': 'abr 25 2020 12:00:00:000', 'Valor': '999.00'},
            {'Codigo': account.code, 'Centro': 'DIC-TEST-2020', 'Subcentro': 'OTRO',
             'Fecha': 'abr 25 2020 12:00:00:000', 'Valor': '999.00'},
            {'Codigo': 'OTRA-CUENTA', 'Centro': 'DIC-TEST-2020', 'Subcentro': 'GDE',
             'Fecha': 'abr 25 2020 12:00:00:000', 'Valor': '999.00'},
        ]
        selected = self.sync._rows_for_saved_lines(rows, line)
        self.assertEqual(len(selected), 3)
        self.assertEqual(sum(float(item['Valor']) for item in selected), 1059.0)
        self.assertEqual(len(self.sync._rows_for_saved_lines(rows, line)), 3)

    def test_sincronizacion_catalogo_registros_existentes_no_repite_codigos(self):
        """Regresión del error unique(company_id, code) reportado por el ERP."""
        account = self.account_model.with_context(active_test=False).create({
            'company_id': self.company.id, 'code': '601010101001-EXIST',
            'name': 'Nombre original', 'active': False,
        })
        center = self.center_model.with_context(active_test=False).create({
            'company_id': self.company.id, 'code': 'MAT-EXIST',
            'name': 'Centro original', 'active': False,
        })
        result_account = self.sync._sync_accounts(self.company, [
            {'Codigo': '601010101001-EXIST', 'Nombre': 'Sueldos y Salarios'},
        ])
        result_center = self.sync._sync_centers(self.company, [
            {'Codigo': 'MAT-EXIST      ', 'Nombre': 'MAT- ALB - NEXUS      '},
        ])
        self.assertEqual(result_account['created'], 0)
        self.assertEqual(result_center['created'], 0)
        self.assertTrue(account.active)
        self.assertTrue(center.active)
        self.assertEqual(account.name, 'Sueldos y Salarios')
        self.assertEqual(center.name, 'MAT- ALB - NEXUS')
