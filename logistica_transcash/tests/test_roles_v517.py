"""Pruebas V5.17: permisos efectivos en los modelos, sin depender del menú."""
from odoo.tests.common import TransactionCase
from odoo.exceptions import AccessError


class TestRolesOperativosV517(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        operator_group = cls.env.ref('logistica_transcash.group_transcash_operador_rutas')
        driver_group = cls.env.ref('logistica_transcash.group_transcash_chofer')
        internal = cls.env.ref('base.group_user')
        portal = cls.env.ref('base.group_portal')
        cls.operator = cls.env['res.users'].sudo().create({
            'name': 'V517 Operador', 'login': 'test-operator-v517@example.invalid',
            'groups_id': [(6, 0, [internal.id, operator_group.id])],
            'company_ids': [(6, 0, [cls.env.company.id])],
        })
        cls.driver = cls.env['res.users'].sudo().create({
            'name': 'V517 Chofer', 'login': 'test-driver-v517@example.invalid',
            'groups_id': [(6, 0, [portal.id, driver_group.id])],
        })
        cls.transport = cls.env['res.partner'].create({'name':'Empresa de transporte v517'})
        cls.destination = cls.env['transcash.destino'].sudo().create({
            'company_id': cls.env.company.id, 'codigo': 'TEST-V517',
            'name': 'Destino V517', 'ciudad': 'Destino V517',
        })

    def test_operator_can_create_route_but_cannot_modify_tariffs(self):
        self.assertTrue(self.operator.has_group('logistica_transcash.group_transcash_operador_rutas'))
        self.assertFalse(self.operator.share)
        route = self.env['transcash.hoja.ruta'].with_user(self.operator).create({
            'company_id': self.env.company.id, 'chofer_usuario_id': self.driver.id,
            'proveedor_id': self.transport.id, 'destino_id': self.destination.id,
            'placa': 'GYA-517', 'tipo_vehiculo': 'camion',
        })
        self.assertEqual(route.state, 'borrador')
        with self.assertRaises(AccessError):
            self.env['transcash.tarifa.traslado'].with_user(self.operator).create({
                'company_id': self.env.company.id,
                'tipo_vehiculo': 'camion', 'destino_id': self.destination.id, 'precio': 250,
            })

    def test_portal_driver_cannot_plan_routes(self):
        with self.assertRaises(AccessError):
            self.env['transcash.hoja.ruta'].with_user(self.driver).create({
                'company_id': self.env.company.id, 'chofer_usuario_id': self.driver.id,
                'proveedor_id': self.transport.id, 'destino_id': self.destination.id,
                'placa': 'GYA-517', 'tipo_vehiculo': 'camion',
            })
        with self.assertRaises(AccessError):
            self.env['transcash.embarque'].with_user(self.driver).create_from_guides([])

    def test_operator_reads_only_its_companies(self):
        company2 = self.env['res.company'].sudo().create({'name': 'V517 Otra compañía'})
        other = self.env['transcash.hoja.ruta'].sudo().create({
            'company_id': company2.id, 'chofer_usuario_id': self.driver.id,
            'proveedor_id': self.transport.id, 'destino_id':
                self.env['transcash.destino'].sudo().create({
                    'company_id': company2.id, 'codigo': 'V517-COMP2',
                    'name': 'Destino compañía2'}).id,
            'placa': 'GYA-518', 'tipo_vehiculo': 'camion',
        })
        result = self.env['transcash.hoja.ruta'].with_user(self.operator).search([('id','=',other.id)])
        self.assertFalse(result)
