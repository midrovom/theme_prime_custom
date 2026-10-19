# -*- coding: utf-8 -*-
"""Regresión para sincronización ERP por lotes, sin hacer peticiones de red."""
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestERPBatches1468(TransactionCase):
    def setUp(self):
        super().setUp()
        self.sync = self.env['expense.budget.inventory.sync']
        self.company = self.env.company

    def test_lotes_catalogos_idempotentes_y_no_borran_rubros(self):
        accounts = [
            {'Codigo': 'BATCH68-A%04d   ' % n, 'Nombre': 'Cuenta %s' % n}
            for n in range(530)
        ]
        centers = [
            {'Codigo': 'BATCH68-C%04d   ' % n, 'Nombre': 'Centro %s' % n}
            for n in range(510)
        ]
        created_a = self.sync._sync_accounts(self.company, accounts)
        created_c = self.sync._sync_centers(self.company, centers)
        self.assertEqual(created_a['created'], 530)
        self.assertEqual(created_c['created'], 510)
        self.assertEqual(self.sync._sync_accounts(self.company, accounts)['unchanged'], 530)
        self.assertEqual(self.sync._sync_centers(self.company, centers)['unchanged'], 510)

        category = self.env['expense.budget.category'].create({
            'company_id': self.company.id, 'name': 'Rubro ERP lotes',
        })
        account = self.env['expense.budget.account'].search([
            ('company_id', '=', self.company.id), ('code', '=', 'BATCH68-A0001'),
        ], limit=1)
        category.write({'account_selection_ids': [(6, 0, [account.id])]})
        accounts[1]['Nombre'] = 'Cuenta renombrada desde ERP'
        centers[1]['Nombre'] = 'Centro renombrado desde ERP'
        self.assertEqual(self.sync._sync_accounts(self.company, accounts)['updated'], 1)
        self.assertEqual(self.sync._sync_centers(self.company, centers)['updated'], 1)
        self.assertEqual(account.category_id, category)
        self.assertEqual(account.name, 'Cuenta renombrada desde ERP')
        self.assertEqual(self.env['expense.budget.account'].search_count([
            ('company_id', '=', self.company.id), ('code', '=', account.code),
        ]), 1)

    def test_subcentros_de_varios_anios_sin_duplicar(self):
        center = self.env['expense.budget.cost.center'].create({
            'company_id': self.company.id, 'code': 'BATCH68-CC', 'name': 'Centro lote',
        })
        rows = [
            {'Codigo': 'BATCH68-A', 'Fecha': 'abr 7 2020 12:00:00:000',
             'Valor': '10.00', 'Centro': 'BATCH68-CC  ', 'Subcentro': 'GDE    '},
            {'Codigo': 'BATCH68-A', 'Fecha': 'abr 7 2026 12:00:00:000',
             'Valor': '20.00', 'Centro': 'BATCH68-CC', 'Subcentro': 'GDE'},
            {'Codigo': 'BATCH68-A', 'Fecha': 'jul 7 2026 12:00:00:000',
             'Valor': '30.00', 'Centro': 'BATCH68-CC', 'Subcentro': 'VTA'},
        ]
        self.assertEqual(self.sync._sync_subcenters(self.company, rows)['created'], 2)
        self.assertEqual(self.sync._sync_subcenters(self.company, rows)['unchanged'], 2)
        self.assertEqual(self.env['expense.budget.subcenter'].search_count([
            ('company_id', '=', self.company.id), ('center_id', '=', center.id),
        ]), 2)
