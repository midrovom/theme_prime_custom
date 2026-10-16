"""Pruebas de regresión V5.9 (requieren runner Odoo 18)."""
from odoo.tests.common import TransactionCase
from odoo.exceptions import AccessError, UserError, ValidationError


class TestHojasRuta(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.manager = cls.env.ref('base.user_admin')
        cls.manager.sudo().write({'groups_id': [(4,cls.env.ref('logistica_transcash.group_logistica_manager').id)]})
        cls.driver = cls.env['res.users'].sudo().create({
            'name':'Chofer Test Rutas', 'login':'tc-driver-v59@example.invalid',
            'email':'tc-driver-v59@example.invalid',
            'groups_id':[(6,0,[cls.env.ref('base.group_portal').id,
                               cls.env.ref('logistica_transcash.group_transcash_chofer').id])],
        })
        cls.vendor = cls.env['res.partner'].create({'name':'Empresa transportista V59'})
        cls.customer = cls.env['res.partner'].create({'name':'Destinatario V59'})
        cls.destino = cls.env['transcash.destino'].with_user(cls.manager).create({
            'company_id':cls.env.company.id,'codigo':'EC-QUI','name':'Quito',
            'ciudad':'Quito', 'provincia':'Pichincha'})
        cls.env['transcash.tarifa.traslado'].with_user(cls.manager).create({
            'company_id':cls.env.company.id, 'tipo_vehiculo':'camion',
            'destino_id':cls.destino.id, 'precio':125.0})
        cls.guide = cls.env['transcash.guia'].sudo().create({
            'name':'TEST-59-01', 'company_id':cls.env.company.id,
            'chofer_usuario_id':cls.driver.id,'proveedor_id':cls.vendor.id,
            'destinatario_id':cls.customer.id,'placa':'ABC-999',
            'destino_codigo':'EC-QUI', 'destino':'Quito',
        })

    def test_driver_cannot_create_embark_or_upload_loading(self):
        with self.assertRaises(AccessError):
            self.env['transcash.embarque'].with_user(self.driver).create_from_guides([self.guide.id])
        with self.assertRaises(AccessError):
            self.env['transcash.evidencia'].with_user(self.driver).register_evidence(
                self.guide, 'carga', 'Cargando', False, False, False)

    def test_logistics_plan_requires_video_and_driver_accepts(self):
        route = self.env['transcash.hoja.ruta'].with_user(self.manager).create({
            'company_id':self.env.company.id, 'chofer_usuario_id':self.driver.id,
            'proveedor_id':self.vendor.id, 'placa':'ABC-999',
            'tipo_vehiculo':'camion', 'destino_id':self.destino.id,
            'seleccion_guia_ids':[(6,0,[self.guide.id])],
        })
        route.with_user(self.manager).action_confirm_route()
        self.assertEqual(route.state,'planificada')
        self.assertEqual(route.tarifa_referencial,125.0)
        wiz = self.env['transcash.armar.embarque.wizard'].with_user(self.manager).create({
            'ruta_ids':[(6,0,[route.id])]})
        # Antes de registrar, el operador conoce el valor que va a generar.
        self.assertEqual(wiz.importe_nuevas_rutas, 125.0)
        self.assertEqual(wiz.importe_rutas_existentes, 0.0)
        self.assertEqual(wiz.importe_total_estimado, 125.0)
        wiz.action_confirm()
        emb = route.embarque_id
        self.assertTrue(emb)
        # Después de registrar, ambos importes están visibles en el backoffice.
        self.assertEqual(emb.tarifa_referencial_total, 125.0)
        self.assertEqual(emb.valor_acordado, 125.0)
        with self.assertRaises(UserError):
            emb.with_user(self.manager).action_ready_for_driver()
        with self.assertRaises(UserError):
            emb.with_user(self.driver).action_accept_and_depart()
        # Entrada declarada imitando un video MP4 válido mínimo (no medio audiovisual real)
        import base64
        fake_mp4 = b'\x00\x00\x00\x18ftypisom'+b'\x00'*20
        route.with_user(self.manager).write({
            'video_carga':base64.b64encode(fake_mp4), 'video_nombre':'prueba.mp4'})
        route.with_user(self.manager).action_validate_video()
        emb.with_user(self.manager).action_ready_for_driver()
        self.assertEqual(emb.state,'embarcado')
        emb.with_user(self.driver).action_accept_and_depart()
        self.assertEqual(emb.state,'ruta')
        self.assertEqual(self.guide.state,'ruta')
        self.assertTrue(emb.aceptado_chofer)

    def test_registro_con_ruta_adicional_actualiza_el_resumen(self):
        """La suma por ruta se actualiza sin contar dos veces las ya asignadas."""
        ruta1 = self.env['transcash.hoja.ruta'].with_user(self.manager).create({
            'company_id':self.env.company.id, 'chofer_usuario_id':self.driver.id,
            'proveedor_id':self.vendor.id, 'placa':'ABC-999',
            'tipo_vehiculo':'camion', 'destino_id':self.destino.id,
            'seleccion_guia_ids':[(6,0,[self.guide.id])],
        })
        ruta1.with_user(self.manager).action_confirm_route()
        first_wizard = self.env['transcash.armar.embarque.wizard'].with_user(self.manager).create({
            'ruta_ids':[(6,0,[ruta1.id])]})
        first_wizard.action_confirm()
        emb = ruta1.embarque_id
        guide2 = self.env['transcash.guia'].sudo().create({
            'name':'TEST-59-02', 'company_id':self.env.company.id,
            'chofer_usuario_id':self.driver.id,'proveedor_id':self.vendor.id,
            'destinatario_id':self.customer.id,'placa':'ABC-999',
            'destino_codigo':'EC-QUI', 'destino':'Quito',
        })
        ruta2 = self.env['transcash.hoja.ruta'].with_user(self.manager).create({
            'company_id':self.env.company.id, 'chofer_usuario_id':self.driver.id,
            'proveedor_id':self.vendor.id, 'placa':'ABC-999',
            'tipo_vehiculo':'camion', 'destino_id':self.destino.id,
            'seleccion_guia_ids':[(6,0,[guide2.id])],
        })
        ruta2.with_user(self.manager).action_confirm_route()
        second_wizard = self.env['transcash.armar.embarque.wizard'].with_user(self.manager).create({
            'embarque_id':emb.id, 'ruta_ids':[(6,0,[ruta2.id])]})
        self.assertEqual(second_wizard.importe_nuevas_rutas, 125.0)
        self.assertEqual(second_wizard.importe_rutas_existentes, 125.0)
        self.assertEqual(second_wizard.importe_total_estimado, 250.0)
        second_wizard.action_confirm()
        self.assertEqual(emb.tarifa_referencial_total, 250.0)
        self.assertEqual(emb.valor_acordado, 250.0)
