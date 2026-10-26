# -*- coding: utf-8 -*-
"""Un presupuesto por (empresa, año, rubro), no uno por empresa/año."""
from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestBudgetUniqueRubro1479(TransactionCase):

    def setUp(self):
        super().setUp()
        self.company = self.env.company
        self.Rubro = self.env['expense.budget.category']
        self.Budget = self.env['expense.budget'].with_context(
            skip_expense_budget_consumption_on_save=True,
        )
        self.Line = self.env['expense.budget.line'].with_context(
            skip_expense_budget_consumption_on_save=True,
        )
        self.rubro_a = self.Rubro.create({
            'code': 'TEST-1479-A', 'name': 'Servicios', 'company_id': self.company.id,
        })
        self.rubro_b = self.Rubro.create({
            'code': 'TEST-1479-B', 'name': 'Administración', 'company_id': self.company.id,
        })
        self.account_a = self.env['expense.budget.account'].create({
            'code': 'TEST-1479-CTA-A', 'name': 'Agua',
            'company_id': self.company.id, 'category_id': self.rubro_a.id,
        })
        self.account_b = self.env['expense.budget.account'].create({
            'code': 'TEST-1479-CTA-B', 'name': 'Papelería',
            'company_id': self.company.id, 'category_id': self.rubro_b.id,
        })

    def _budget(self, rubro, year=2088):
        return self.Budget.create({
            'company_id': self.company.id, 'year': year,
            'category_id': rubro.id, 'name': 'Presupuesto %s' % rubro.name,
        })

    def test_varios_rubros_en_el_mismo_anio_incluso_en_borrador(self):
        a = self._budget(self.rubro_a)
        b = self._budget(self.rubro_b)
        self.assertEqual((a.state, b.state), ('draft', 'draft'))
        self.assertEqual(a.year, b.year)
        self.assertNotEqual(a.category_id, b.category_id)

    def test_unico_rubro_anio_cualquier_estado(self):
        a = self._budget(self.rubro_a)
        with self.assertRaises(ValidationError):
            with self.env.cr.savepoint():
                self._budget(self.rubro_a)
        self.assertEqual(a.state, 'draft')
        # Un año distinto sí permite presupuestar el mismo rubro.
        another_year = self._budget(self.rubro_a, year=2089)
        self.assertNotEqual(a.id, another_year.id)

    def test_sin_rubro_no_se_puede_crear(self):
        with self.assertRaises(ValidationError):
            self.Budget.create({
                'company_id': self.company.id, 'year': 2088, 'name': 'Sin rubro',
            })

    def test_no_permite_cambiar_a_rubro_ya_presupuestado(self):
        a = self._budget(self.rubro_a)
        b = self._budget(self.rubro_b)
        with self.assertRaises(ValidationError):
            with self.env.cr.savepoint():
                b.write({'category_id': a.category_id.id})
        self.assertEqual(b.category_id, self.rubro_b)

    def test_lineas_solo_del_rubro_seleccionado(self):
        a = self._budget(self.rubro_a)
        good = self.Line.create({
            'budget_id': a.id, 'account_id': self.account_a.id,
            'month': '2', 'planned_amount': 100,
        })
        self.assertEqual(good.category_id, self.rubro_a)
        with self.assertRaises(ValidationError):
            with self.env.cr.savepoint():
                self.Line.create({
                    'budget_id': a.id, 'account_id': self.account_b.id,
                    'month': '2', 'planned_amount': 100,
                })

    def test_year_and_company_alter_uniqueness_key(self):
        self._budget(self.rubro_a, year=2091)
        future = self._budget(self.rubro_b, year=2092)
        with self.assertRaises(ValidationError):
            with self.env.cr.savepoint():
                future.write({'category_id': self.rubro_a.id, 'year': 2091})
        self.assertEqual(future.year, 2092)
