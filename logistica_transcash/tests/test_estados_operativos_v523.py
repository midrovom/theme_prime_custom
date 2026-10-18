"""V5.23: un mismo estado operativo de ruta para escritorio Odoo y PWA.

Los estados de CARGA/ACEPTACIÓN se conservan en route.state para auditoría y
la visualización usa route.estado_operativo (dependiente de cierres de guías).
Ejecutar con la batería de tests de Odoo 18 en una base aislada.
"""
from odoo import fields
from odoo.tests.common import TransactionCase


class TestEstadoOperativoCompartidoV523(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.driver = cls.env['res.users'].sudo().create({
            'name': 'Chofer sincronización V523',
            'login': 'v523.driver@example.invalid',
            'groups_id': [(6, 0, [cls.env.ref('base.group_portal').id,
                                    cls.env.ref('logistica_transcash.group_transcash_chofer').id])],
        })
        cls.supplier = cls.env['res.partner'].sudo().create({'name': 'Transportista V523'})
        cls.customer = cls.env['res.partner'].sudo().create({'name': 'Destinatario V523'})
        cls.destination = cls.env['transcash.destino'].sudo().create({
            'codigo': 'T-V523', 'name': 'Destino V523', 'company_id': cls.env.company.id,
        })

    def _make_trip(self, guide_counts=(2, 1)):
        trip = self.env['transcash.embarque'].sudo().create({
            'company_id': self.env.company.id,
            'chofer_usuario_id': self.driver.id,
            'proveedor_id': self.supplier.id,
            'placa': 'V523', 'state': 'preparacion',
        })
        routes, guides = [], []
        for route_no, n in enumerate(guide_counts, 1):
            route = self.env['transcash.hoja.ruta'].sudo().create({
                'company_id': self.env.company.id,
                'chofer_usuario_id': self.driver.id,
                'proveedor_id': self.supplier.id,
                'placa': 'V523', 'tipo_vehiculo': 'camion',
                'destino_id': self.destination.id, 'embarque_id': trip.id,
                'state': 'cargada',
            })
            routes.append(route)
            for j in range(n):
                guides.append(self.env['transcash.guia'].sudo().create({
                    'name': f'V523-{route_no}-{j}',
                    'company_id': self.env.company.id,
                    'destinatario_id': self.customer.id,
                    'chofer_usuario_id': self.driver.id,
                    'proveedor_id': self.supplier.id,
                    'hoja_ruta_id': route.id,
                    'embarque_id': trip.id, 'state': 'embarcada',
                }))
        return trip, routes, guides

    def test_preparation_acceptance_and_partial_delivery(self):
        trip, routes, guides = self._make_trip()
        self.assertEqual(routes[0].estado_operativo, 'cargada')
        self.assertEqual(trip.rutas_total, 2)
        self.assertEqual(trip.rutas_entregadas, 0)
        trip.sudo().write({'state': 'embarcado'})
        self.assertTrue(all(r.estado_operativo == 'pendiente_aceptacion' for r in routes))
        # Se conserva state=aceptada como evidencia de aceptación del chofer.
        for r in routes:
            r.sudo().write({'state': 'aceptada'})
        for g in guides:
            g.sudo().write({'state': 'ruta'})
        trip.sudo().write({'state': 'ruta', 'aceptado_chofer': True})
        self.assertEqual(routes[0].estado_operativo, 'en_ruta')
        stamp = fields.Datetime.now()
        guides[0].sudo().write({'state': 'revision', 'fecha_cierre_chofer': stamp})
        trip._refresh_delivered_state()
        self.assertEqual(routes[0].estado_operativo, 'en_entrega')
        self.assertEqual(trip.state, 'ruta')
        guides[1].sudo().write({'state': 'revision', 'fecha_cierre_chofer': stamp})
        trip._refresh_delivered_state()
        self.assertEqual(routes[0].estado_operativo, 'entregada')
        self.assertEqual(routes[0].state, 'aceptada')  # hito histórico intacto
        self.assertEqual(routes[1].estado_operativo, 'en_ruta')
        self.assertEqual(trip.rutas_entregadas, 1)
        guides[2].sudo().write({'state': 'revision', 'fecha_cierre_chofer': stamp})
        trip._refresh_delivered_state()
        self.assertEqual(trip.state, 'entregado')
        self.assertEqual(trip.rutas_entregadas, trip.rutas_total)
        self.assertFalse(trip.estado_rutas_inconsistente)
        self.assertTrue(all(r.estado_operativo == 'entregada' for r in routes))
        self.assertTrue(all(g.state == 'revision' for g in guides))  # recepción cliente posterior

    def test_viaje_historico_entregado_con_estado_aceptada(self):
        trip, routes, guides = self._make_trip((1,))
        # Simula un registro de V5.22: la ruta quedó aceptada, pero las guías
        # y el viaje ya estaban cerrados. No requiere migración ni sobreescritura.
        routes[0].sudo().write({'state': 'aceptada'})
        guides[0].sudo().write({'state': 'revision', 'fecha_cierre_chofer': fields.Datetime.now()})
        trip.sudo().write({'state': 'entregado'})
        self.assertEqual(routes[0].estado_operativo, 'entregada')
        self.assertEqual(routes[0].state, 'aceptada')
        self.assertEqual(trip.rutas_entregadas, 1)
        self.assertFalse(trip.estado_rutas_inconsistente)

    def test_viaje_historico_inconsistente_no_oculta_una_entrega_faltante(self):
        trip, routes, guides = self._make_trip((1, 1))
        for route in routes:
            route.sudo().write({'state': 'aceptada'})
        guides[0].sudo().write({'state': 'revision', 'fecha_cierre_chofer': fields.Datetime.now()})
        trip.sudo().write({'state': 'entregado'})
        self.assertEqual(routes[0].estado_operativo, 'entregada')
        self.assertEqual(routes[1].estado_operativo, 'revisar')
        self.assertEqual(trip.rutas_entregadas, 1)
        self.assertTrue(trip.estado_rutas_inconsistente)

    def test_viaje_sin_rutas_legacy_no_dispara_falso_positivo(self):
        trip, _, _ = self._make_trip(())
        trip.sudo().write({'state': 'entregado'})
        self.assertEqual(trip.rutas_total, 0)
        self.assertFalse(trip.estado_rutas_inconsistente)
