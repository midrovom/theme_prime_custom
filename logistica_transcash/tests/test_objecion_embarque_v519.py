"""Flujo interno de objeción (requiere Odoo 18 --test-enable)."""
import base64
from odoo.tests.common import TransactionCase
from odoo.exceptions import AccessError, UserError, ValidationError


class TestObjecionCargaV519(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.manager = cls.env.ref('base.user_admin')
        cls.manager.sudo().write({'groups_id':[(4,cls.env.ref('logistica_transcash.group_logistica_manager').id)]})
        cls.driver = cls.env['res.users'].sudo().create({
            'name':'Chofer Objeciones 519', 'login':'v519-chofer@example.invalid',
            'groups_id':[(6,0,[cls.env.ref('base.group_portal').id,
                               cls.env.ref('logistica_transcash.group_transcash_chofer').id])],
        })
        cls.other_driver = cls.env['res.users'].sudo().create({
            'name':'Chofer no asignado 519', 'login':'v519-no-asignado@example.invalid',
            'groups_id':[(6,0,[cls.env.ref('base.group_portal').id,
                               cls.env.ref('logistica_transcash.group_transcash_chofer').id])],
        })
        cls.carrier = cls.env['res.partner'].create({'name':'Proveedor carga 519'})
        cls.client = cls.env['res.partner'].create({'name':'Cliente 519'})
        cls.destino = cls.env['transcash.destino'].with_user(cls.manager).create({
            'company_id':cls.env.company.id,'codigo':'TEST-V519','name':'Destino objeciones'})
        cls.env['transcash.tarifa.traslado'].with_user(cls.manager).create({
            'company_id':cls.env.company.id,'tipo_vehiculo':'camion',
            'destino_id':cls.destino.id,'precio':130})

    def _setup_trip(self):
        guide = self.env['transcash.guia'].sudo().create({
            'name':'TEST-OBJ-519', 'company_id':self.env.company.id,
            'chofer_usuario_id':self.driver.id,'proveedor_id':self.carrier.id,
            'destinatario_id':self.client.id,'placa':'GYE-519',
            'destino_id':self.destino.id,'destino_codigo':self.destino.codigo,
            'destino':self.destino.name})
        ruta = self.env['transcash.hoja.ruta'].with_user(self.manager).create({
            'company_id':self.env.company.id,'chofer_usuario_id':self.driver.id,
            'proveedor_id':self.carrier.id,'placa':'GYE-519',
            'tipo_vehiculo':'camion','destino_id':self.destino.id,
            'seleccion_guia_ids':[(6,0,[guide.id])]})
        ruta.with_user(self.manager).action_confirm_route()
        self.env['transcash.armar.embarque.wizard'].with_user(self.manager).create({
            'ruta_ids':[(6,0,[ruta.id])]}).action_confirm()
        return ruta.embarque_id, ruta, guide

    def _evidence(self, route):
        img = b'\xff\xd8\xff\xe0' + b'\x00'*80
        return self.env['transcash.carga.evidencia.ruta'].with_user(self.manager).create({
            'ruta_id':route.id,'archivo':base64.b64encode(img),
            'nombre':'foto-v519.jpg','tipo':'foto','mime':'image/jpeg',
        })

    def test_reject_correct_and_depart_with_audit(self):
        trip, route, guide = self._setup_trip()
        self._evidence(route)
        trip.with_user(self.manager).action_ready_for_driver()
        with self.assertRaises(ValidationError):
            trip.with_user(self.driver).action_report_discrepancy('Falta')
        with self.assertRaises(AccessError):
            trip.with_user(self.other_driver).action_report_discrepancy('El contenido de la carga difiere')
        trip.with_user(self.driver).action_report_discrepancy('No corresponde la mercancía de la guía')
        self.assertTrue(trip.objecion_pendiente)
        self.assertEqual(len(trip.objecion_ids),1)
        self.assertEqual(trip.objecion_ids[0].chofer_id,self.driver)
        with self.assertRaises(UserError):
            trip.with_user(self.driver).action_accept_and_depart()
        with self.assertRaises(UserError):
            trip.with_user(self.manager).action_ready_for_driver()
        trip.with_user(self.manager).action_reopen_packing()
        self.assertTrue(trip.objecion_pendiente)
        with self.assertRaises(UserError):
            trip.with_user(self.manager).action_resolve_discrepancy(
                'Se verificó nuevamente la carga del transporte')
        self._evidence(route)
        trip.with_user(self.manager).action_resolve_discrepancy(
            'Se reemplazó la mercadería y se capturó nueva evidencia')
        self.assertFalse(trip.objecion_pendiente)
        self.assertEqual(trip.objecion_ids[0].estado,'resuelta')
        self.assertEqual(trip.objecion_ids[0].responsable_id,self.manager)
        self.assertTrue(trip.objecion_ids[0].explicacion_resolucion)
        trip.with_user(self.manager).action_ready_for_driver()
        trip.with_user(self.driver).action_accept_and_depart()
        self.assertEqual(trip.state,'ruta')
        self.assertFalse(guide.evento_ids.filtered(lambda e:
            e.publico_cliente and ('Chofer aceptó carga' in e.accion or 'Carga evidenciada por Logística' in e.accion)))

    def test_customer_cannot_see_or_edit_internal_log(self):
        trip, route, guide = self._setup_trip()
        portal = self.env['res.users'].sudo().create({
            'name':'Cliente Portal 519','login':'v519-cliente@example.invalid',
            'groups_id':[(6,0,[self.env.ref('base.group_portal').id,
                               self.env.ref('logistica_transcash.group_transcash_cliente').id])],
        })
        with self.assertRaises(AccessError):
            self.env['transcash.embarque.objecion'].with_user(portal).create({
                'embarque_id':trip.id,'chofer_id':self.driver.id,'motivo':'No coincide'})
        with self.assertRaises(AccessError):
            trip.with_user(portal).write({'objecion_pendiente':True})
