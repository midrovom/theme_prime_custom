"""V5.27: el flete se aprueba tras cierre operativo, sin esperar al cliente.

Ejecutar con el runner de Odoo 18, no son pruebas de navegador.
"""
from odoo import fields
from odoo.tests.common import TransactionCase
from odoo.exceptions import AccessError, UserError


class TestAprobacionIndependienteV527(TransactionCase):
    def setUp(self):
        super().setUp()
        self.carrier = self.env['res.partner'].sudo().create({'name': 'Transportista V527', 'is_company': True})
        carrier_contact = self.env['res.partner'].sudo().create({
            'name': 'Portal Proveedor V527', 'parent_id': self.carrier.id})
        self.supplier = self.env['res.users'].sudo().with_context(no_reset_password=True).create({
            'name': 'Portal Proveedor V527', 'login': 'proveedor.v527@example.invalid',
            'partner_id': carrier_contact.id,
            'groups_id': [(6, 0, [self.env.ref('base.group_portal').id,
                                    self.env.ref('logistica_transcash.group_transcash_transportista').id])],
        })
        self.manager = self.env['res.users'].sudo().with_context(no_reset_password=True).create({
            'name': 'Jefe Logística V527', 'login': 'jefe.v527@example.invalid',
            'groups_id': [(6, 0, [self.env.ref('logistica_transcash.group_logistica_manager').id])],
        })
        self.accountant = self.env['res.users'].sudo().with_context(no_reset_password=True).create({
            'name': 'Contabilidad V527', 'login': 'conta.v527@example.invalid',
            'groups_id': [(6, 0, [self.env.ref('logistica_transcash.group_transcash_contabilidad').id])],
        })
        self.driver = self.env['res.users'].sudo().with_context(no_reset_password=True).create({
            'name': 'Chofer V527', 'login': 'chofer.v527@example.invalid',
            'groups_id': [(6, 0, [self.env.ref('base.group_portal').id,
                                    self.env.ref('logistica_transcash.group_transcash_chofer').id])],
        })
        self.dest = self.env['transcash.destino'].sudo().create({
            'codigo': 'V527-UIO', 'name': 'Destino pruebas 527', 'company_id': self.env.company.id,
        })
        self.trip = self.env['transcash.embarque'].sudo().create({
            'name': 'EMB-V527-001', 'company_id': self.env.company.id,
            'chofer_usuario_id': self.driver.id, 'proveedor_id': self.carrier.id,
            'placa': 'V527-ABC', 'state': 'entregado', 'valor_acordado': 180.0,
        })
        self.route = self.env['transcash.hoja.ruta'].sudo().create({
            'company_id': self.env.company.id, 'chofer_usuario_id': self.driver.id,
            'proveedor_id': self.carrier.id, 'placa': 'V527-ABC', 'tipo_vehiculo': 'camion',
            'destino_id': self.dest.id, 'embarque_id': self.trip.id, 'state': 'aceptada',
        })
        self.guide = self.env['transcash.guia'].sudo().create({
            'name': 'GUIA-V527-001', 'company_id': self.env.company.id,
            'chofer_usuario_id': self.driver.id, 'proveedor_id': self.carrier.id,
            'embarque_id': self.trip.id, 'hoja_ruta_id': self.route.id,
            'state': 'revision', 'fecha_cierre_chofer': fields.Datetime.now(),
            'aprobacion_global': 'pendiente', 'incidencia_estado': 'abierta',
            'resultado_recepcion': 'pendiente',
        })

    def test_aprobacion_no_espera_aceptacion_cliente_ni_incidente(self):
        self.assertEqual(self.route.estado_entrega, 'completa')
        self.trip.with_user(self.manager).action_approve_transport()
        self.assertEqual(self.trip.estado_aprobacion, 'aprobado')
        self.assertFalse(self.trip.aprobacion_excepcional)
        self.assertEqual(self.guide.state, 'revision')
        self.assertEqual(self.guide.incidencia_estado, 'abierta')
        self.assertEqual(self.guide.aprobacion_global, 'pendiente')
        self.assertEqual(self.trip.aprobado_por_id, self.manager)
        self.assertTrue(self.trip.aprobado_fecha)
        self.assertIn('publicado al proveedor', ' '.join(self.trip.message_ids.mapped('body')))
        document = self.env['transcash.pago.liquidacion'].with_user(self.supplier).create_supplier_liquidation([self.trip.id])
        self.assertEqual(len(document.linea_ids), 1)
        self.assertEqual(document.total_acordado, 180.0)
        with self.assertRaises(UserError):
            self.trip.with_user(self.manager).action_approve_transport()

    def test_solo_jefe_logistica_puede_aprobar(self):
        with self.assertRaises(AccessError):
            self.trip.with_user(self.accountant).action_approve_transport()
        with self.assertRaises(AccessError):
            self.trip.with_user(self.driver).action_approve_transport()
        self.assertEqual(self.trip.estado_aprobacion, 'pendiente')

    def test_cierre_de_guia_y_ruta_sigue_siendo_obligatorio(self):
        self.guide.sudo().write({'state': 'destino', 'fecha_cierre_chofer': False})
        with self.assertRaises(UserError):
            self.trip.with_user(self.manager).action_approve_transport()
        self.guide.sudo().write({'state': 'revision', 'fecha_cierre_chofer': fields.Datetime.now()})
        self.guide.sudo().write({'hoja_ruta_id': False})
        with self.assertRaises(UserError):
            self.trip.with_user(self.manager).action_approve_transport()
        self.assertEqual(self.trip.estado_aprobacion, 'pendiente')

    def test_precio_positivo_y_viaje_entregado_obligatorios(self):
        self.trip.sudo().write({'valor_acordado': 0.0})
        with self.assertRaises(UserError):
            self.trip.with_user(self.manager).action_approve_transport()
        self.trip.sudo().write({'valor_acordado': 180.0, 'state': 'ruta'})
        with self.assertRaises(UserError):
            self.trip.with_user(self.manager).action_approve_transport()

    def test_cliente_puede_confirmar_despues_del_flete(self):
        self.trip.with_user(self.manager).action_approve_transport()
        self.assertEqual(self.guide.resultado_recepcion, 'pendiente')
        self.assertEqual(self.trip.estado_financiero, 'aprobado')
        # La aprobación del viaje no adelanta ni oculta el estado del cliente.
        self.assertFalse(self.guide.fecha_entrega)
