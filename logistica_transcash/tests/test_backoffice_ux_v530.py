"""Odoo 18 regression tests for V5.30 backend navigation and security.

Run on a throwaway copy: --test-enable -u logistica_transcash
No invoice is posted in native account.move; Transcash is documentary.
"""
from odoo.tests.common import TransactionCase
from odoo.exceptions import AccessError


class TestBackofficeUxV530(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.accountant = cls.env['res.users'].sudo().with_context(no_reset_password=True).create({
            'name': 'V530 Accountant', 'login': 'v530.accountant@example.invalid',
            'company_id': cls.company.id, 'company_ids': [(6, 0, [cls.company.id])],
            'groups_id': [(6, 0, [cls.env.ref('logistica_transcash.group_transcash_contabilidad').id])],
        })
        cls.supplier = cls.env['res.partner'].sudo().create({
            'name': 'V530 Supplier', 'is_company': True,
        })
        cls.document = cls.env['transcash.pago.liquidacion'].sudo().create({
            'company_id': cls.company.id, 'proveedor_id': cls.supplier.id,
        })

    def test_accounting_navigation(self):
        action = self.env.ref('logistica_transcash.action_tc_accounting_desk_v530')
        self.assertEqual(action.res_model, 'transcash.pago.liquidacion')
        self.assertTrue(action.view_mode.startswith('kanban,'))
        self.assertEqual(action.search_view_id, self.env.ref(
            'logistica_transcash.view_transcash_liquidacion_search_v530'))
        self.assertEqual(self.env.ref('logistica_transcash.menu_transcash_pago_liquidaciones').parent_id,
                         self.env.ref('logistica_transcash.menu_tc_accounting_v530'))
        self.assertFalse(self.env.ref('logistica_transcash.menu_transcash_pagos').active)

    def test_accountant_can_open_related_trips_and_payments(self):
        doc = self.document.with_user(self.accountant)
        trips = doc.action_open_trips()
        self.assertEqual(trips['res_model'], 'transcash.embarque')
        self.assertEqual(trips['domain'], [('id', 'in', [])])
        self.assertFalse(trips['context']['edit'])
        pays = doc.action_open_payments()
        self.assertEqual(pays['res_model'], 'transcash.pago.registro')
        self.assertEqual(pays['domain'], [('liquidacion_id', '=', self.document.id)])
        self.assertFalse(pays['context']['create'])

    def test_portal_cannot_open_accounting_drilldowns(self):
        user = self.env.ref('base.public_user')
        with self.assertRaises(AccessError):
            self.document.with_user(user).action_open_trips()
        with self.assertRaises(AccessError):
            self.document.with_user(user).action_open_payments()

    def test_kanban_and_financial_view_scope(self):
        cards = self.env.ref('logistica_transcash.view_transcash_liquidacion_kanban_v530')
        trips = self.env.ref('logistica_transcash.view_transcash_embarque_kanban_v530')
        routes = self.env.ref('logistica_transcash.view_transcash_ruta_kanban_v530')
        self.assertIn('t-name="card"', cards.arch_db)
        self.assertIn('saldo_pendiente', cards.arch_db)
        self.assertIn('fecha_entrega', trips.arch_db)
        self.assertNotIn('valor_acordado', trips.arch_db)
        self.assertNotIn('tarifa_referencial', routes.arch_db)
