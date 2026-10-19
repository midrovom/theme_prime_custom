"""V5.32: navegación real en menú contable y kanban enlazado a acciones.
Ejecutar en base de pruebas Odoo 18, nunca sobre datos productivos.
"""
from odoo.tests.common import TransactionCase


class TestBackofficeV532(TransactionCase):
    def test_legacy_navigation_off_after_update(self):
        for xml_id in ('menu_transcash_pagos', 'menu_transcash_activas',
                       'menu_transcash_incidentes', 'menu_transcash_carga'):
            record = self.env.ref('logistica_transcash.' + xml_id)
            self.assertFalse(record.active, xml_id)
        # No se elimina el histórico de liquidaciones ni la selección de guías.
        self.assertIn('transcash.pago.liquidacion', self.env)
        self.assertTrue(self.env.ref('logistica_transcash.menu_transcash_guias').active)

    def test_accounting_menu_opens_financial_workspace(self):
        menu = self.env.ref('logistica_transcash.menu_tc_accounting_v530')
        desk = self.env.ref('logistica_transcash.action_tc_accounting_desk_v530')
        self.assertEqual(menu.action, desk)
        root = self.env.ref('logistica_transcash.menu_transcash_root')
        group = self.env.ref('logistica_transcash.group_transcash_contabilidad')
        self.assertIn(group, root.groups_id)

    def test_kanban_explicitly_linked_to_every_primary_action(self):
        targets = {
            'action_tc_accounting_desk_v530': 'view_transcash_liquidacion_kanban_v530',
            'action_transcash_pago_liquidaciones': 'view_transcash_liquidacion_kanban_v530',
            'action_transcash_facturas_recibidas': 'view_transcash_liquidacion_kanban_v530',
            'action_transcash_embarques': 'view_transcash_embarque_kanban_v530',
            'action_transcash_rutas': 'view_transcash_ruta_kanban_v530',
            'action_tc_payments_v530': 'view_tc_transfer_kanban_v532',
            'action_transcash_acceso_proveedores': 'view_tc_proveedores_kanban_v532',
            'action_transcash_acceso_clientes': 'view_tc_clientes_kanban_v532',
            'action_transcash_chofer': 'view_tc_chofer_kanban_v532',
            'action_transcash_novedades': 'view_tc_novedades_kanban_v532',
        }
        for action_xmlid, view_xmlid in targets.items():
            action = self.env.ref('logistica_transcash.' + action_xmlid)
            view = self.env.ref('logistica_transcash.' + view_xmlid)
            links = action.view_ids.filtered(lambda r: r.view_mode == 'kanban')
            self.assertTrue(links, action_xmlid)
            self.assertIn(view, links.mapped('view_id'))
            self.assertTrue(action.view_mode.startswith('kanban,'), action_xmlid)

    def test_guide_planning_not_removed(self):
        action = self.env.ref('logistica_transcash.action_tc_guias_planificar_v531')
        self.assertEqual(action.res_model, 'transcash.guia')
        self.assertTrue(self.env.ref('logistica_transcash.menu_transcash_guias').active)
