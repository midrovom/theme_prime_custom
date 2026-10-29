# -*- coding: utf-8 -*-
"""El gráfico por centro/rubro/cuenta/mes usa las mismas líneas y filtros."""
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestDashboardByCostCenter(TransactionCase):
    def setUp(self):
        super().setUp()
        self.company = self.env.company
        Category = self.env['expense.budget.category']
        Account = self.env['expense.budget.account']
        Center = self.env['expense.budget.cost.center']
        Budget = self.env['expense.budget']
        Line = self.env['expense.budget.line']
        self.rubro_a = Category.create({
            'company_id': self.company.id, 'code': 'DASH-1497-A',
            'name': 'Servicios',
        })
        self.rubro_b = Category.create({
            'company_id': self.company.id, 'code': 'DASH-1497-B',
            'name': 'Transporte',
        })
        self.luz = Account.create({
            'company_id': self.company.id, 'code': 'DASH-LUZ-1497',
            'name': 'Luz 1497', 'category_id': self.rubro_a.id,
        })
        self.agua = Account.create({
            'company_id': self.company.id, 'code': 'DASH-AGUA-1497',
            'name': 'Agua 1497', 'category_id': self.rubro_a.id,
        })
        self.flete = Account.create({
            'company_id': self.company.id, 'code': 'DASH-FLETE-1497',
            'name': 'Fletes 1497', 'category_id': self.rubro_b.id,
        })
        self.center_a = Center.create({
            'company_id': self.company.id, 'code': 'DASH-CENT-A-1497',
            'name': 'Administración 1497',
        })
        self.center_b = Center.create({
            'company_id': self.company.id, 'code': 'DASH-CENT-B-1497',
            'name': 'Operaciones 1497',
        })
        b_a = Budget.create({
            'company_id': self.company.id, 'name': 'Dashboard servicios 2078',
            'year': 2078, 'category_id': self.rubro_a.id,
        })
        b_b = Budget.create({
            'company_id': self.company.id, 'name': 'Dashboard transporte 2078',
            'year': 2078, 'category_id': self.rubro_b.id,
        })
        for budget, account, center, month, amount in (
            (b_a, self.luz, self.center_a, '1', 25.1256),
            (b_a, self.agua, self.center_a, '1', 14.5),
            (b_a, self.luz, self.center_b, '1', 60.25),
            (b_a, self.luz, self.center_b, '2', 10.125),
            (b_b, self.flete, self.center_a, '1', 100.0),
            (b_a, self.agua, False, '2', 9.125),
        ):
            Line.create({
                'budget_id': budget.id, 'account_id': account.id,
                'cost_center_id': center.id if center else False,
                'month': month, 'planned_amount': 200,
                'manual_actual_amount': amount,
            })

    def _payload(self, center=False):
        return self.env['expense.budget.dashboard'].get_dashboard_data(
            self.company.id, 2078, center,
        )

    def test_all_centers_broken_down_without_losing_month_or_rubro(self):
        payload = self._payload()
        data = payload['breakdown']
        self.assertEqual(len(data), 6)
        self.assertEqual({row['center_id'] for row in data},
                         {self.center_a.id, self.center_b.id, -1})
        self.assertEqual({row['category_id'] for row in data},
                         {self.rubro_a.id, self.rubro_b.id})
        self.assertAlmostEqual(sum(row['months'][0] for row in data), 199.8756)
        self.assertAlmostEqual(sum(row['months'][1] for row in data), 19.25)
        self.assertAlmostEqual(sum(sum(row['months']) for row in data),
                               sum(sum(a['months']) for a in payload['accounts']))
        self.assertIn(-1, [c['id'] for c in payload['cost_centers']])

    def test_center_filter_keeps_other_account_options(self):
        payload = self._payload(self.center_a.id)
        self.assertEqual(payload['cost_center_id'], self.center_a.id)
        self.assertEqual({r['center_id'] for r in payload['breakdown']}, {self.center_a.id})
        self.assertAlmostEqual(sum(sum(r['months']) for r in payload['breakdown']), 139.6256)
        self.assertEqual({c['id'] for c in payload['categories']},
                         {self.rubro_a.id, self.rubro_b.id})
        self.assertEqual({a['id'] for a in payload['accounts']},
                         {self.luz.id, self.agua.id, self.flete.id})
        self.assertAlmostEqual(sum(sum(a['months']) for a in payload['accounts']), 139.6256)
        payload_b = self._payload(self.center_b.id)
        self.assertAlmostEqual(sum(sum(r['months']) for r in payload_b['breakdown']), 70.375)

    def test_unassigned_center_is_not_all_centers(self):
        payload = self._payload(-1)
        self.assertEqual(payload['cost_center_id'], -1)
        self.assertEqual(len(payload['breakdown']), 1)
        self.assertEqual(payload['breakdown'][0]['center_id'], -1)
        self.assertAlmostEqual(payload['breakdown'][0]['months'][1], 9.125)
        self.assertEqual(sum(payload['breakdown'][0]['months'][:1]), 0.0)

    def test_invalid_center_cannot_bypass_company(self):
        with self.assertRaises(AccessError):
            self._payload(999999999)
