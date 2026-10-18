"""Regresión V5.25: una hoja de ruta expone sólo sus propios archivos.

Ejecutar dentro de Odoo 18 con --test-enable sobre base de pruebas.
"""
import base64
from odoo.tests.common import TransactionCase
from odoo.exceptions import AccessError
from ..controllers.evidence_hub import gallery_for_route, gallery_for_trip


class TestVisorRutaV525(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.destinos = cls.env['transcash.destino'].sudo()
        cls.carrier = cls.env['res.partner'].sudo().create({'name': 'Transportista V525'})
        cls.clients = [cls.env['res.partner'].sudo().create({'name': 'Receptor V525 A'}),
                       cls.env['res.partner'].sudo().create({'name': 'Receptor V525 B'})]
        cls.driver = cls.env['res.users'].sudo().create({
            'name': 'Chofer V525', 'login': 'v525-driver@example.invalid',
            'groups_id': [(6, 0, [cls.env.ref('base.group_portal').id,
                                  cls.env.ref('logistica_transcash.group_transcash_chofer').id])],
        })
        cls.internal = cls.env['res.users'].sudo().create({
            'name': 'Auditor interno V525', 'login': 'v525-internal@example.invalid',
            'groups_id': [(6, 0, [cls.env.ref('base.group_user').id,
                                  cls.env.ref('logistica_transcash.group_transcash_consulta').id])],
        })
        cls.customer = cls.env['res.users'].sudo().create({
            'name': 'Cliente V525', 'login': 'v525-customer@example.invalid',
            'partner_id': cls.clients[0].id,
            'groups_id': [(6, 0, [cls.env.ref('base.group_portal').id,
                                  cls.env.ref('logistica_transcash.group_transcash_cliente').id])],
        })

    def _records(self):
        trip = self.env['transcash.embarque'].sudo().create({
            'company_id': self.env.company.id, 'chofer_usuario_id': self.driver.id,
            'proveedor_id': self.carrier.id, 'placa': 'V525-001', 'state': 'ruta',
        })
        routes = self.env['transcash.hoja.ruta'].sudo()
        guides = self.env['transcash.guia'].sudo()
        picture = base64.b64encode(b'\xff\xd8\xff\xe0' + b'x' * 40).decode('ascii')
        for n in range(2):
            dest = self.destinos.create({'name': 'V525 destino %d' % n,
                                         'codigo': 'V525-%d' % n,
                                         'company_id': self.env.company.id})
            route = self.env['transcash.hoja.ruta'].sudo().create({
                'company_id': self.env.company.id, 'destino_id': dest.id,
                'chofer_usuario_id': self.driver.id, 'proveedor_id': self.carrier.id,
                'placa': 'V525-001', 'tipo_vehiculo': 'camion',
                'state': 'aceptada', 'embarque_id': trip.id,
            })
            routes |= route
            guide = self.env['transcash.guia'].sudo().create({
                'name': 'V525 GUIA-%d' % n, 'company_id': self.env.company.id,
                'destinatario_id': self.clients[n].id, 'chofer_usuario_id': self.driver.id,
                'proveedor_id': self.carrier.id, 'embarque_id': trip.id,
                'hoja_ruta_id': route.id, 'state': 'ruta',
            })
            guides |= guide
            self.env['transcash.evidencia'].sudo().create({
                'guia_id': guide.id, 'tipo': 'llegada',
                'archivo': picture, 'archivo_mime': 'image/jpeg',
                'archivo_nombre': 'descarga-v525-%d.jpg' % n,
            })
        return trip, routes, guides

    def test_route_gallery_restricts_to_own_guides(self):
        trip, routes, guides = self._records()
        first = gallery_for_route(routes[0])
        second = gallery_for_route(routes[1])
        self.assertEqual(len(first['gallery_routes']), 1)
        self.assertEqual(first['gallery_routes'][0]['name'], routes[0].name)
        self.assertEqual(len(first['gallery_descarga']), 1)
        self.assertEqual(len(second['gallery_descarga']), 1)
        self.assertIn('GUIA-0', first['gallery_descarga'][0]['subtitle'])
        self.assertNotIn('GUIA-1', str(first['gallery_routes']))
        self.assertIn('GUIA-1', second['gallery_descarga'][0]['subtitle'])
        self.assertEqual(len(gallery_for_trip(trip)['gallery_routes']), 2)
        self.assertNotIn('valor_acordado', first)

    def test_customer_has_no_backoffice_gallery_permission(self):
        trip, routes, guides = self._records()
        with self.assertRaises(AccessError):
            routes[0].with_user(self.customer).action_open_route_gallery()
        with self.assertRaises(AccessError):
            guides[0].with_user(self.customer)._check_internal_gallery_access()
        self.assertTrue(routes[0].with_user(self.internal).action_open_route_gallery()['url'].endswith(
            '/backoffice/rutas/%d/galeria' % routes[0].id))
