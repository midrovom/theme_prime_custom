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
        self.assertEqual(route.tarifa_referencial, 0.0)  # La ruta no tiene flete propio
        wiz = self.env['transcash.armar.embarque.wizard'].with_user(self.manager).create({
            'ruta_ids':[(6,0,[route.id])]})
        # Antes de registrar, el operador conoce el valor que va a generar.
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
        """Añadir rutas NO vuelve a cobrar el traslado por el mismo camión."""
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
        self.assertEqual(second_wizard.importe_total_estimado, 125.0)
        second_wizard.action_confirm()
        self.assertEqual(emb.tarifa_referencial_total, 125.0)
        self.assertEqual(emb.valor_acordado, 125.0)


    def test_sin_tarifa_por_ruta_hasta_crear_embarque(self):
        """Se puede confirmar una ruta hacia un destino aún sin tarifa."""
        sin_tarifa = self.env['transcash.destino'].with_user(self.manager).create({
            'company_id': self.env.company.id, 'codigo': 'EC-NOTAR-V516',
            'name': 'Destino sin tarifa V516',
        })
        guide = self.env['transcash.guia'].sudo().create({
            'name': 'V516-G-NOTAR', 'company_id': self.env.company.id,
            'chofer_usuario_id': self.driver.id, 'proveedor_id': self.vendor.id,
            'destinatario_id': self.customer.id, 'placa': 'ABC-999',
            'destino_id': sin_tarifa.id, 'destino_codigo': sin_tarifa.codigo,
        })
        route = self.env['transcash.hoja.ruta'].with_user(self.manager).create({
            'company_id': self.env.company.id, 'chofer_usuario_id': self.driver.id,
            'proveedor_id': self.vendor.id, 'placa': 'ABC-999',
            'tipo_vehiculo': 'camion', 'destino_id': sin_tarifa.id,
            'seleccion_guia_ids': [(6, 0, [guide.id])],
        })
        route.with_user(self.manager).action_confirm_route()
        self.assertEqual(route.state, 'planificada')
        self.assertFalse(route.tarifa_id)
        self.assertEqual(route.tarifa_referencial, 0.0)
        wizard = self.env['transcash.armar.embarque.wizard'].with_user(self.manager).create({
            'ruta_ids': [(6, 0, [route.id])],
        })
        with self.assertRaisesRegex(UserError, 'No hay precio por viaje'):
            wizard.action_confirm()
        self.assertFalse(route.embarque_id)

    def test_dos_destinos_un_solo_precio_y_snapshot(self):
        """El destino de cobro lo escoge Logística, no se suman destinos."""
        otro_destino = self.env['transcash.destino'].with_user(self.manager).create({
            'company_id': self.env.company.id, 'codigo': 'EC-CUE-V516',
            'name': 'Cuenca V516',
        })
        other_rate = self.env['transcash.tarifa.traslado'].with_user(self.manager).create({
            'company_id': self.env.company.id, 'tipo_vehiculo': 'camion',
            'destino_id': otro_destino.id, 'precio': 400.0,
        })
        def mk_route(suffix, destination, guide):
            r = self.env['transcash.hoja.ruta'].with_user(self.manager).create({
                'company_id': self.env.company.id, 'chofer_usuario_id': self.driver.id,
                'proveedor_id': self.vendor.id, 'placa': 'ABC-999',
                'tipo_vehiculo': 'camion', 'destino_id': destination.id,
                'seleccion_guia_ids': [(6, 0, [guide.id])],
            })
            r.with_user(self.manager).action_confirm_route()
            return r
        route1 = mk_route('1', self.destino, self.guide)
        guide2 = self.env['transcash.guia'].sudo().create({
            'name': 'V516-G-CUE', 'company_id': self.env.company.id,
            'chofer_usuario_id': self.driver.id, 'proveedor_id': self.vendor.id,
            'destinatario_id': self.customer.id, 'placa': 'ABC-999',
            'destino_id': otro_destino.id, 'destino_codigo': otro_destino.codigo,
        })
        route2 = mk_route('2', otro_destino, guide2)
        vals = {'ruta_ids': [(6, 0, [route1.id, route2.id])]}
        no_dest = self.env['transcash.armar.embarque.wizard'].with_user(self.manager).create(vals)
        self.assertEqual(no_dest.importe_total_estimado, 0.0)
        with self.assertRaisesRegex(UserError, 'Seleccione el destino de cobro'):
            no_dest.action_confirm()
        wiz = self.env['transcash.armar.embarque.wizard'].with_user(self.manager).create({
            **vals, 'destino_cobro_id': otro_destino.id,
        })
        self.assertEqual(wiz.importe_total_estimado, 400.0)
        wiz.action_confirm()
        trip = route1.embarque_id
        self.assertEqual(trip, route2.embarque_id)
        self.assertEqual(trip.destino_tarifa_id, otro_destino)
        self.assertEqual(trip.tarifa_id, other_rate)
        self.assertEqual(trip.tarifa_referencial_total, 400.0)
        self.assertEqual(trip.valor_acordado, 400.0)
        other_rate.with_user(self.manager).write({'precio': 480.0})
        self.assertEqual(trip.tarifa_referencial_total, 400.0)
        self.assertEqual(trip.valor_acordado, 400.0)

    def test_operador_no_puede_cambiar_precio_registrado_por_rpc(self):
        route = self.env['transcash.hoja.ruta'].with_user(self.manager).create({
            'company_id': self.env.company.id, 'chofer_usuario_id': self.driver.id,
            'proveedor_id': self.vendor.id, 'placa': 'ABC-999',
            'tipo_vehiculo': 'camion', 'destino_id': self.destino.id,
            'seleccion_guia_ids': [(6, 0, [self.guide.id])],
        })
        route.with_user(self.manager).action_confirm_route()
        wiz = self.env['transcash.armar.embarque.wizard'].with_user(self.manager).create({
            'ruta_ids': [(6, 0, [route.id])],
        })
        wiz.action_confirm()
        from odoo.exceptions import AccessError
        with self.assertRaises(AccessError):
            route.embarque_id.with_user(self.driver).write({'tarifa_referencial_total': 999.0})

    def test_revisar_tarifa_historica_sin_alterar_valor_acordado(self):
        route = self.env['transcash.hoja.ruta'].with_user(self.manager).create({
            'company_id': self.env.company.id, 'chofer_usuario_id': self.driver.id,
            'proveedor_id': self.vendor.id, 'placa': 'ABC-999',
            'tipo_vehiculo': 'camion', 'destino_id': self.destino.id,
            'seleccion_guia_ids': [(6, 0, [self.guide.id])],
        })
        route.with_user(self.manager).action_confirm_route()
        self.env['transcash.armar.embarque.wizard'].with_user(self.manager).create({
            'ruta_ids': [(6, 0, [route.id])],
        }).action_confirm()
        trip = route.embarque_id
        # Simular un precio histórico registrado cuando se sumaban las rutas.
        trip.sudo().write({'tarifa_referencial_total': 250.0, 'valor_acordado': 250.0})
        wiz = self.env['transcash.corregir.tarifa.embarque.wizard'].with_user(self.manager).create({
            'embarque_id': trip.id, 'destino_cobro_id': self.destino.id,
            'actualizar_valor_acordado': False,
        })
        wiz.action_confirm()
        self.assertEqual(trip.tarifa_referencial_total, 125.0)
        self.assertEqual(trip.valor_acordado, 250.0)  # Jamás cambia por omisión.
        new_wiz = self.env['transcash.corregir.tarifa.embarque.wizard'].with_user(self.manager).create({
            'embarque_id': trip.id, 'destino_cobro_id': self.destino.id,
            'actualizar_valor_acordado': True,
        })
        new_wiz.action_confirm()
        self.assertEqual(trip.valor_acordado, 125.0)
