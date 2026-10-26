# -*- coding: utf-8 -*-
"""Rubro en cabecera y presupuesto único por código/empresa/año."""
from lxml import etree
from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestRubroHeader1480(TransactionCase):

    def setUp(self):
        super().setUp()
        self.company = self.env.company
        self.Rubro = self.env['expense.budget.category']
        self.Budget = self.env['expense.budget'].with_context(
            skip_expense_budget_consumption_on_save=True)
        self.Account = self.env['expense.budget.account']
        self.Line = self.env['expense.budget.line'].with_context(
            skip_expense_budget_consumption_on_save=True)
        self.basic = self.Rubro.create({
            'code': 'SB-1480', 'name': 'Servicio básico', 'company_id': self.company.id})
        self.trans = self.Rubro.create({
            'code': 'TRA-1480', 'name': 'Transporte', 'company_id': self.company.id})
        self.water = self.Account.create({
            'code': 'AG-1480', 'name': 'Agua', 'company_id': self.company.id,
            'category_id': self.basic.id})
        self.vehicle = self.Account.create({
            'code': 'VH-1480', 'name': 'Vehículo', 'company_id': self.company.id,
            'category_id': self.trans.id})

    def _create(self, rubro, year=2085):
        return self.Budget.create({
            'name': 'Prueba ' + rubro.name, 'company_id': self.company.id,
            'year': year, 'category_id': rubro.id})

    def test_same_year_different_codes_even_with_draft(self):
        first = self._create(self.basic)
        second = self._create(self.trans)
        self.assertEqual(first.state, 'draft')
        self.assertEqual(second.state, 'draft')
        self.assertNotEqual(first.category_id.code, second.category_id.code)

    def test_same_rubro_code_blocked_regardless_of_state(self):
        self._create(self.basic)
        with self.assertRaises(ValidationError):
            with self.env.cr.savepoint():
                self._create(self.basic)
        self.assertTrue(self._create(self.basic, year=2086))

    def test_category_code_is_unique_case_insensitive(self):
        with self.assertRaises(ValidationError):
            with self.env.cr.savepoint():
                self.Rubro.create({
                    'name': 'Otro servicio', 'code': ' sb-1480 ',
                    'company_id': self.company.id})

    def test_rubro_header_not_in_monthly_grid(self):
        view = self.env.ref('expense_budget_control.view_expense_budget_form')
        root = etree.fromstring(view.arch_db.encode())
        groups = root.xpath("//form/sheet/group/group[1]/field")
        order = [node.get('name') for node in groups]
        self.assertEqual(order[order.index('year') + 1], 'category_id')
        lines = root.xpath("//field[@name='line_ids']/list")
        self.assertEqual(len(lines), 1)
        self.assertFalse(lines[0].xpath("./field[@name='category_id']"))
        account = lines[0].xpath("./field[@name='account_id']")[0]
        self.assertIn("('category_id', '=', parent.category_id)", account.get('domain'))

    def test_lines_receive_header_category_without_editing_rubro(self):
        budget = self._create(self.basic)
        line = self.Line.create({
            'budget_id': budget.id, 'account_id': self.water.id,
            'month': '1', 'planned_amount': 100,
        })
        self.assertEqual(line.category_id, budget.category_id)
        with self.assertRaises(ValidationError):
            with self.env.cr.savepoint():
                self.Line.create({
                    'budget_id': budget.id, 'account_id': self.vehicle.id,
                    'month': '2', 'planned_amount': 100,
                })

    def test_repeat_same_rubro_on_write(self):
        budget = self._create(self.basic)
        self.Line.create({
            'budget_id': budget.id, 'account_id': self.water.id,
            'month': '3', 'planned_amount': 110,
        })
        # No debe bloquear imprimir/guardar si cliente reenvía la categoría igual.
        budget.write({'category_id': budget.category_id.id})
        self.assertEqual(budget.category_id, self.basic)
