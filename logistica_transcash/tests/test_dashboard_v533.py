"""Pruebas reales de v5.33. Se ejecutan con Odoo --test-enable."""
from datetime import timedelta
from odoo import fields
from odoo.tests.common import TransactionCase
from odoo.exceptions import AccessError


class TestDashboardV533(TransactionCase):
    def setUp(self):
        super().setUp()
        self.model = self.env['transcash.dashboard.service']
        self.analyst = self.env['res.users'].with_context(no_reset_password=True).create({
            'name':'Analista Dashboard 533', 'login':'analyst.v533@example.invalid',
            'groups_id':[(6,0,[self.env.ref('logistica_transcash.group_transcash_dashboard').id])]})
        self.partner = self.env['res.partner'].create({'name':'Transportadora Dashboard 533'})

    def _today(self):
        return fields.Date.context_today(self.model).isoformat()

    def test_registro_incluye_guias_sin_embarque(self):
        self.env['transcash.guia'].sudo().create({
            'name':'GUIA/TEST/533', 'company_id':self.env.company.id,
            'proveedor_id':self.partner.id, 'destino':'Quito', 'state':'registrada'})
        result = self.model.with_user(self.analyst).get_dashboard('dia', self._today(), self._today(), 'registro')
        self.assertGreaterEqual(result['kpis']['guias'],1)
        self.assertGreaterEqual(result['kpis']['guias_sin_ruta'],1)
        self.assertTrue(any(r['nombre']=='GUIA/TEST/533' for r in result['guias']))

    def test_dashboard_general_no_filtra_datos_comerciales(self):
        result = self.model.with_user(self.analyst).get_dashboard('mes', self._today(), self._today(), 'registro')
        self.assertFalse(result['permisos']['comercial'])
        self.assertNotIn('marcas',result)
        self.assertNotIn('proveedores_producto',result)
        self.assertNotIn('liquidaciones',result)

    def test_valida_fechas(self):
        with self.assertRaises(Exception):
            self.model.with_user(self.analyst).get_dashboard('semana','2026-12-31','2026-01-01')

    def test_menu_dashboard_integrado(self):
        menu = self.env.ref('logistica_transcash.menu_transcash_dashboard')
        self.assertEqual(menu.parent_id, self.env.ref('logistica_transcash.menu_transcash_root'))
        self.assertEqual(menu.action, self.env.ref('logistica_transcash.action_transcash_dashboard'))
        self.assertEqual(self.env.ref('logistica_transcash.menu_transcash_root').action, menu.action)
