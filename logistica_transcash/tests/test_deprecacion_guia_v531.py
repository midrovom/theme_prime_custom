"""V5.31: los menús y acciones obsoletos dejan de ofrecer control financiero por guía.

Ejecutar en instancia Odoo 18 de pruebas después de -u logistica_transcash.
"""
from odoo.tests.common import TransactionCase


class TestDeprecacionGuiaV531(TransactionCase):
    def test_legacy_menus_are_deactivated_not_deleted(self):
        for xmlid in ('menu_transcash_pagos', 'menu_transcash_activas',
                      'menu_transcash_incidentes', 'menu_transcash_carga'):
            menu = self.env.ref('logistica_transcash.' + xmlid)
            self.assertTrue(menu.exists(), xmlid)
            self.assertFalse(menu.active, xmlid)

    def test_legacy_actions_no_longer_navigate_to_guide_finances(self):
        actions = {
            'action_transcash_payment': 'transcash.pago.liquidacion',
            'action_transcash_open': 'transcash.embarque',
            'action_transcash_incidencias': 'transcash.novedad.resumen',
        }
        for xmlid, model in actions.items():
            self.assertEqual(self.env.ref('logistica_transcash.' + xmlid).res_model, model)

    def test_route_planning_still_uses_guides(self):
        menu = self.env.ref('logistica_transcash.menu_transcash_guias')
        self.assertTrue(menu.active)
        action = self.env.ref('logistica_transcash.action_tc_guias_planificar_v531')
        self.assertEqual(action.res_model, 'transcash.guia')
        self.assertIn(('state', '=', 'registrada'), action.domain if isinstance(action.domain, list)
                      else __import__('ast').literal_eval(action.domain))
        self.assertEqual(menu.action, action)
        routes = self.env['transcash.hoja.ruta']
        self.assertIn('guia_ids', routes._fields)
        self.assertIn('seleccion_guia_ids', routes._fields)
        self.assertTrue(callable(routes.action_open_guide_selector))

    def test_no_legacy_loading_buttons_in_guide_form(self):
        form = self.env.ref('logistica_transcash.view_transcash_guia_form').arch_db
        self.assertNotIn('name="action_start_loading"', form)
        self.assertNotIn('name="action_depart"', form)
        self.assertIn('action_open_evidence_gallery', form)

    def test_accounting_and_root_navigation(self):
        self.assertEqual(self.env.ref('logistica_transcash.menu_transcash_root').action,
                         self.env.ref('logistica_transcash.action_transcash_embarques'))
        self.assertTrue(self.env.ref('logistica_transcash.menu_transcash_pago_liquidaciones').active)
        self.assertEqual(self.env.ref('logistica_transcash.action_tc_accounting_desk_v530').res_model,
                         'transcash.pago.liquidacion')

    def test_legacy_wizard_models_and_guides_remain_for_history(self):
        # Compatibilidad deliberada: esconder no equivale a borrar datos del usuario.
        self.assertIn('transcash.liquidacion.wizard', self.env)
        self.assertIn('transcash.embarque.liquidacion.wizard', self.env)
        self.assertIn('transcash.guia', self.env)
        self.assertIn('transcash.pago.liquidacion', self.env)
