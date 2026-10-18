"""V5.5 - cierre del chofer con nombre obligatorio y revisión simplificada.
Debe ejecutarse dentro de Odoo 18 con --test-enable.
"""
from odoo.exceptions import UserError
from .test_cierre_chofer_v54 import TestCierreChofer


class TestRecepcionSimpleV55(TestCierreChofer):
    def test_driver_name_is_mandatory(self):
        guia = self.guides[0]
        self._arrive_with_photo(guia)
        for invalid in ('', ' ', '12'):
            with self.assertRaises(UserError):
                guia.sudo().with_user(self.driver).sudo().action_close_driver_delivery('', invalid)
            self.assertFalse(guia.fecha_cierre_chofer)
        guia.sudo().with_user(self.driver).sudo().action_close_driver_delivery('', 'María Herrera')
        self.assertEqual(guia.persona_presente_chofer, 'María Herrera')
        self.assertEqual(guia.resultado_recepcion, 'pendiente')
        self.assertFalse(guia.fecha_entrega)

    def test_client_conforme_approves_pending_media_once(self):
        guia = self.guides[0]
        evidence = self._arrive_with_photo(guia)
        guia.sudo().with_user(self.driver).sudo().action_close_driver_delivery('', 'Lucía Mora')
        self.assertEqual(evidence.estado, 'pendiente')
        guia.sudo().with_user(self.client).sudo().action_confirm_delivery('Lucía Mora', '', 'conforme')
        self.assertEqual(evidence.estado, 'aprobada')
        self.assertEqual(guia.resultado_recepcion, 'conforme')
        self.assertEqual(guia.state, 'entregada')
        self.assertEqual(guia.persona_presente_chofer, 'Lucía Mora')
        self.assertTrue(guia.fecha_cierre_chofer)

    def test_client_reports_novedad_without_blocking_driver(self):
        guia = self.guides[0]
        evidence = self._arrive_with_photo(guia)
        guia.sudo().with_user(self.driver).sudo().action_close_driver_delivery('', 'Roberto Cruz')
        with self.assertRaises(UserError):
            guia.sudo().with_user(self.client).sudo().action_confirm_delivery('Roberto Cruz', 'No', 'con_novedades')
        guia.sudo().with_user(self.client).sudo().action_confirm_delivery(
            'Roberto Cruz', 'Dos cajas llegaron mojadas; se adjuntará evidencia.', 'con_novedades')
        self.assertEqual(guia.resultado_recepcion, 'con_novedades')
        self.assertEqual(guia.incidencia_estado, 'abierta')
        self.assertEqual(guia.state, 'entregada')
        self.assertEqual(evidence.estado, 'aprobada')
        # El embarque todavía tiene otra guía sin cerrar: ese motivo operativo
        # (no la incidencia del cliente) es lo que impide aprobarlo.
        with self.assertRaises(UserError):
            self.trip._ensure_finance_ready()

    def test_incidencia_blocks_conforme(self):
        guia = self.guides[0]
        self._arrive_with_photo(guia)
        guia.sudo().with_user(self.driver).sudo().action_close_driver_delivery('', 'Ana Sánchez')
        guia.sudo()._open_incident('Faltante documentado')
        with self.assertRaises(UserError):
            guia.sudo().with_user(self.client).sudo().action_confirm_delivery('Ana Sánchez', '', 'conforme')
        self.assertEqual(guia.state, 'revision')
        self.assertFalse(guia.fecha_entrega)
