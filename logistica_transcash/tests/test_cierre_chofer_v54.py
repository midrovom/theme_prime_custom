"""V5.4: cierre operativo independiente de aceptación posterior del cliente.
Ejecutar en una base de pruebas Odoo 18 con --test-enable.
"""
from odoo import fields
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError


class TestCierreChofer(TransactionCase):
    def setUp(self):
        super().setUp()
        self.driver_partner = self.env['res.partner'].create({'name': 'Chofer V54'})
        self.driver = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Chofer V54', 'login': 'chofer.v54@example.invalid',
            'partner_id': self.driver_partner.id,
            'groups_id': [(6, 0, [self.env.ref('base.group_portal').id,
                                 self.env.ref('logistica_transcash.group_transcash_chofer').id])],
        })
        self.client_partner = self.env['res.partner'].create({'name': 'Cliente V54', 'is_company': True})
        self.client = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Cliente V54', 'login': 'cliente.v54@example.invalid',
            'partner_id': self.client_partner.id,
            'groups_id': [(6, 0, [self.env.ref('base.group_portal').id,
                                 self.env.ref('logistica_transcash.group_transcash_cliente').id])],
        })
        self.other_partner = self.env['res.partner'].create({'name': 'Otro chofer'})
        self.other_driver = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Otro chofer', 'login': 'otrochofer.v54@example.invalid',
            'partner_id': self.other_partner.id,
            'groups_id': [(6, 0, [self.env.ref('base.group_portal').id,
                                 self.env.ref('logistica_transcash.group_transcash_chofer').id])],
        })
        self.supplier = self.env['res.partner'].create({'name': 'Proveedor V54', 'is_company': True})
        self.guides = self.env['transcash.guia'].sudo().create([
            {'name': 'V54-101', 'company_id': self.env.company.id,
             'chofer_usuario_id': self.driver.id, 'destinatario_id': self.client_partner.id,
             'proveedor_id': self.supplier.id, 'placa': 'GYE-1234', 'state': 'registrada'},
            {'name': 'V54-102', 'company_id': self.env.company.id,
             'chofer_usuario_id': self.driver.id, 'destinatario_id': self.client_partner.id,
             'proveedor_id': self.supplier.id, 'placa': 'GYE-1234', 'state': 'registrada'},
        ])
        self.trip = self.env['transcash.embarque'].with_user(self.driver).create_from_guides(self.guides.ids)
        # El caso se concentra en la etapa de entrega, no en el alta de bodega.
        self.trip.sudo().write({'state': 'ruta', 'fecha_salida': fields.Datetime.now()})
        self.guides.sudo().write({'state': 'ruta', 'fecha_salida': fields.Datetime.now()})

    def _arrive_with_photo(self, guide):
        guide.sudo().with_user(self.driver).sudo().action_arrive()
        self.assertEqual(guide.state, 'destino')
        ev = self.env['transcash.evidencia'].with_user(self.driver).register_evidence(
            guide, 'llegada', 'Foto de descarga', 'YQ==', 'foto.jpg', 'image/jpeg')
        # La evidencia no implica aceptación ni cierre del chofer.
        self.assertEqual(guide.state, 'destino')
        self.assertEqual(ev.estado, 'pendiente')
        return ev

    def test_driver_can_finish_and_client_react_later(self):
        first, second = self.guides[0], self.guides[1]
        ev_first = self._arrive_with_photo(first)
        ev_second = self._arrive_with_photo(second)
        first.sudo().with_user(self.driver).sudo().action_close_driver_delivery('Entregado sin observaciones', 'María Paz')
        self.assertEqual(first.state, 'revision')
        self.assertTrue(first.fecha_cierre_chofer)
        self.assertFalse(first.fecha_entrega)
        self.assertEqual(self.trip.state, 'ruta')
        # No se pierde el cierre si la petición se reintenta por falta de señal.
        closure_date = first.fecha_cierre_chofer
        first.sudo().with_user(self.driver).sudo().action_close_driver_delivery('Reintento')
        self.assertEqual(first.fecha_cierre_chofer, closure_date)
        # Segunda entrega cierra el viaje, aunque ambos clientes sigan pendientes.
        second.sudo().with_user(self.driver).sudo().action_close_driver_delivery('', 'Carlos León')
        self.assertEqual(self.trip.state, 'entregado')
        self.assertEqual(self.trip.guias_cerradas_chofer, 2)
        self.assertEqual(self.trip.guias_entregadas, 0)
        # La liquidación del transporte ya puede aprobarse; la revisión del
        # cliente queda separada (no se pierde su derecho a reclamar).
        self.trip._ensure_finance_ready()
        # El cliente sigue pudiendo comentar y adjuntar evidencia después.
        client_evidence = self.env['transcash.evidencia'].with_user(self.client).register_evidence(
            first, 'cliente', 'Llegó una caja golpeada', 'YQ==', 'reclamo.jpg', 'image/jpeg')
        self.assertEqual(client_evidence.autor_usuario_id, self.client)
        ev_first.sudo().with_user(self.client).sudo().action_approve()
        first.sudo().with_user(self.client).sudo().action_confirm_delivery('Receptor de prueba', 'Revisado después')
        self.assertEqual(first.state, 'entregada')
        self.assertEqual(self.trip.state, 'entregado')
        self.assertEqual(self.trip.guias_entregadas, 1)
        self.assertEqual(ev_second.estado, 'pendiente')
        # El chofer ya está libre para un nuevo embarque, sin esperar al cliente.
        later = self.env['transcash.guia'].sudo().create({
            'name': 'V54-103', 'company_id': self.env.company.id, 'chofer_usuario_id': self.driver.id,
            'destinatario_id': self.client_partner.id,
            'proveedor_id': self.supplier.id, 'placa': 'GYE-1234',
        })
        next_trip = self.env['transcash.embarque'].with_user(self.driver).create_from_guides([later.id])
        self.assertEqual(next_trip.state, 'preparacion')
        self.assertNotEqual(self.trip, next_trip)

    def test_cannot_close_without_photo_or_arrival_or_correct_user(self):
        first = self.guides[0]
        with self.assertRaises(UserError):
            first.sudo().with_user(self.driver).sudo().action_close_driver_delivery()
        first.sudo().with_user(self.driver).sudo().action_arrive()
        with self.assertRaises(UserError):
            first.sudo().with_user(self.driver).sudo().action_close_driver_delivery()
        self._arrive_media_direct(first)
        with self.assertRaises(UserError):
            first.sudo().with_user(self.other_driver).sudo().action_close_driver_delivery()
        first.sudo().with_user(self.driver).sudo().action_close_driver_delivery('', 'Ana Rivera')
        with self.assertRaises(UserError):
            self.env['transcash.evidencia'].with_user(self.driver).register_evidence(
                first, 'llegada', 'Intento posterior', 'YQ==', 'foto2.jpg', 'image/jpeg')

    def _arrive_media_direct(self, guide):
        return self.env['transcash.evidencia'].with_user(self.driver).register_evidence(
            guide, 'llegada', 'Descarga final', 'YQ==', 'foto.jpg', 'image/jpeg')
