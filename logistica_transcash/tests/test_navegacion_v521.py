"""Regresión V5.21: la consulta de viajes navega por sus hojas de ruta.

No modifica datos operativos ni prueba el navegador: esa verificación se realiza en VPS.
"""
from odoo.tests.common import TransactionCase


class TestNavegacionJerarquicaV521(TransactionCase):
    def test_embarque_contains_route_hierarchy(self):
        detail = self.env.ref('logistica_transcash.portal_embarque_detalle')
        shared = self.env.ref('logistica_transcash.portal_embarque_ruta_guias')
        self.assertIn('embarque.ruta_ids.sorted', detail.arch_db)
        self.assertIn('portal_embarque_ruta_guias', detail.arch_db)
        self.assertIn('ruta.guia_ids.sorted', shared.arch_db)
        self.assertNotIn('Guías del embarque</h2>', detail.arch_db)

    def test_operator_can_see_same_nested_guide_list(self):
        operations = self.env.ref('logistica_transcash.portal_operacion')
        self.assertIn('tc-ops-route-guides', operations.arch_db)
        self.assertIn('portal_embarque_ruta_guias', operations.arch_db)

    def test_guide_detail_keeps_delivery_actions(self):
        guide_view = self.env.ref('logistica_transcash.portal_guia_detalle')
        self.assertIn('finalizar-entrega', guide_view.arch_db)
        self.assertIn('tc-trip-breadcrumb', guide_view.arch_db)
