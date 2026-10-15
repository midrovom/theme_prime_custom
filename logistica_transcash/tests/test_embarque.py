"""Tests de flujo para ejecutar mediante --test-enable dentro de Odoo 18."""
from odoo.tests.common import TransactionCase
from odoo.exceptions import AccessError, UserError


class TestEmbarques(TransactionCase):
    def setUp(self):
        super().setUp()
        partner = self.env['res.partner'].create({'name':'Conductor de prueba'})
        self.driver = self.env['res.users'].with_context(no_reset_password=True).create({
            'name':'Conductor de prueba', 'login':'conductor.v5.test@example.invalid',
            'partner_id':partner.id,
            'groups_id': [(6,0,[self.env.ref('base.group_portal').id,
                         self.env.ref('logistica_transcash.group_transcash_chofer').id])],
        })
        self.supplier = self.env['res.partner'].create({'name':'Transportes de prueba','is_company':True})
        self.other = self.env['res.partner'].create({'name':'Otra compañía', 'is_company':True})
        self.manager = self.env['res.users'].with_context(no_reset_password=True).create({
            'name':'Responsable de prueba', 'login':'bodega.v5.test@example.invalid',
            'groups_id':[(6,0,[self.env.ref('logistica_transcash.group_logistica_manager').id])],
        })
        self.guide_a = self.env['transcash.guia'].sudo().create({
            'name':'V5-001','company_id':self.env.company.id,'chofer_usuario_id':self.driver.id,
            'proveedor_id':self.supplier.id,'placa':'GYE-001','origen':'Guayaquil',
        })
        self.guide_b = self.env['transcash.guia'].sudo().create({
            'name':'V5-002','company_id':self.env.company.id,'chofer_usuario_id':self.driver.id,
            'proveedor_id':self.supplier.id,'placa':'GYE-001','origen':'Guayaquil',
        })

    def _created(self):
        return self.env['transcash.embarque'].with_user(self.driver).create_from_guides(
            [self.guide_a.id,self.guide_b.id], 'Llegada a bodega')

    def test_group_two_guides_and_prevent_second_travel(self):
        trip = self._created()
        self.assertEqual(len(trip.guia_ids), 2)
        self.assertEqual(trip.state, 'preparacion')
        self.assertEqual(trip.chofer_usuario_id, self.driver)
        with self.assertRaises((UserError,AccessError)):
            self.env['transcash.embarque'].with_user(self.driver).create_from_guides([self.guide_a.id])

    def test_guide_loading_then_departure(self):
        trip = self._created().sudo()
        driver_trip = trip.with_user(self.driver).sudo()
        for guide in (self.guide_a,self.guide_b):
            driver_trip.action_begin_guide(guide.id,'Limpio')
            self.assertEqual(guide.state, 'embarque')
            self.env['transcash.evidencia'].sudo().create({
                'guia_id':guide.id, 'tipo':'carga', 'observacion':'Mercancía en estado adecuado',
                'archivo':'YQ==','estado':'aprobada',
            })
            driver_trip.action_finish_guide(guide.id,'Sin novedades')
        driver_trip.action_mark_embarked()
        self.assertEqual(trip.state, 'embarcado')
        self.assertTrue(all(g.state == 'embarcada' for g in trip.guia_ids))
        trip.with_user(self.manager).sudo().action_depart()
        self.assertEqual(trip.state, 'ruta')
        self.assertTrue(all(g.state == 'ruta' for g in trip.guia_ids))
        self.guide_a.sudo().write({'state':'entregada'})
        trip._refresh_delivered_state()
        self.assertEqual(trip.state,'ruta')
        self.guide_b.sudo().write({'state':'entregada'})
        trip._refresh_delivered_state()
        self.assertEqual(trip.state,'entregado')

    def test_incompatible_supplier_blocked(self):
        self.guide_b.sudo().write({'proveedor_id':self.other.id})
        with self.assertRaises(UserError):
            self._created()

    def test_standard_driver_needs_warehouse_approval(self):
        trip = self._created().sudo().with_user(self.driver).sudo()
        trip.action_begin_guide(self.guide_a.id, 'Estado inicial')
        self.env['transcash.evidencia'].sudo().create({
            'guia_id': self.guide_a.id, 'tipo':'carga',
            'observacion':'Foto registrada', 'archivo':'YQ==', 'estado':'pendiente',
        })
        with self.assertRaises(UserError):
            trip.action_finish_guide(self.guide_a.id)
        self.assertEqual(self.guide_a.state, 'embarque')

    def _enable_autonomous(self):
        driver_entry = self.env['transcash.chofer'].with_user(self.manager).create({
            'usuario_id': self.driver.id, 'company_id': self.env.company.id,
            'carga_autonoma':True,
        })
        self.assertTrue(driver_entry.carga_autonoma)
        return driver_entry

    def test_autonomous_driver_closes_pending_evidence_without_forged_approval(self):
        self._enable_autonomous()
        trip = self._created().sudo().with_user(self.driver).sudo()
        trip.action_begin_guide(self.guide_a.id, 'Carga inicial')
        ev = self.env['transcash.evidencia'].sudo().create({
            'guia_id':self.guide_a.id, 'tipo':'carga', 'observacion':'Foto subida',
            'archivo':'YQ==', 'estado':'pendiente',
        })
        trip.action_finish_guide(self.guide_a.id, 'Carga completa')
        self.assertEqual(self.guide_a.state, 'embarcada')
        self.assertTrue(self.guide_a.cierre_carga_autonomo)
        self.assertEqual(self.guide_a.cierre_carga_usuario_id, self.driver)
        self.assertEqual(ev.estado, 'pendiente')
        self.assertEqual(trip.state,'preparacion')

    def test_autonomous_driver_requires_media_and_rejects_objected_evidence(self):
        self._enable_autonomous()
        trip = self._created().sudo().with_user(self.driver).sudo()
        trip.action_begin_guide(self.guide_a.id)
        with self.assertRaises(UserError):
            trip.action_finish_guide(self.guide_a.id)
        ev = self.env['transcash.evidencia'].sudo().create({
            'guia_id':self.guide_a.id, 'tipo':'carga', 'observacion':'Foto objetada',
            'archivo':'YQ==', 'estado':'objetada',
        })
        with self.assertRaises(UserError):
            trip.action_finish_guide(self.guide_a.id)
        self.assertEqual(ev.estado,'objetada')
        self.assertEqual(self.guide_a.state,'embarque')

    def test_warehouse_user_cannot_assign_autonomous_driver(self):
        warehouse = self.env['res.users'].with_context(no_reset_password=True).create({
            'name':'Almacén de pruebas', 'login':'almacen.v51.test@example.invalid',
            'groups_id':[(6,0,[self.env.ref('logistica_transcash.group_logistica_bodega').id])],
        })
        driver_entry = self._enable_autonomous()
        with self.assertRaises(AccessError):
            driver_entry.with_user(warehouse).write({'carga_autonoma':False})

    def _new_late_guide(self, name='V52-LATE', *, provider=None, plate='GYE-001', driver=None):
        return self.env['transcash.guia'].sudo().create({
            'name': name,
            'company_id': self.env.company.id,
            'chofer_usuario_id': (driver or self.driver).id,
            'proveedor_id': (provider or self.supplier).id,
            'placa': plate,
            'origen': 'Guayaquil',
        })

    def test_driver_can_add_new_guide_to_existing_preparation(self):
        trip = self._created()
        late = self._new_late_guide()
        self.assertEqual(late.state, 'registrada')
        # Una guía que ya estaba cargándose no debe perder su estado.
        trip.with_user(self.driver).action_begin_guide(self.guide_a.id, 'Cargando A')
        trip.with_user(self.driver).action_add_guides([late.id])
        self.assertEqual(late.embarque_id, trip)
        self.assertEqual(late.state, 'registrada')
        self.assertEqual(self.guide_a.state, 'embarque')
        self.assertEqual(len(trip.guia_ids), 3)
        with self.assertRaises(UserError):
            trip.with_user(self.driver).action_add_guides([late.id])
        self.assertEqual(len(trip.guia_ids), 3)

    def test_second_embark_blocked_even_with_different_new_guide(self):
        first = self._created()
        late = self._new_late_guide()
        with self.assertRaises(UserError):
            self.env['transcash.embarque'].with_user(self.driver).create_from_guides([late.id])
        # El rechazo no debe vincular la guía nueva ni crear otro embarque.
        self.assertFalse(late.embarque_id)
        self.assertEqual(first.state, 'preparacion')
        self.assertEqual(self.env['transcash.embarque'].sudo().search_count([
            ('chofer_usuario_id', '=', self.driver.id),
            ('state', 'in', ['preparacion','embarcado','ruta']),
        ]), 1)

    def test_cannot_append_incompatible_supplier_plate_or_driver(self):
        trip = self._created()
        bad_supplier = self._new_late_guide('V52-OTHER-SUPPLIER', provider=self.other)
        bad_plate = self._new_late_guide('V52-OTHER-PLATE', plate='QTO-200')
        for guide in (bad_supplier, bad_plate):
            with self.assertRaises(UserError):
                trip.with_user(self.driver).action_add_guides([guide.id])
            self.assertFalse(guide.embarque_id)

    def test_no_append_after_marking_embarked(self):
        trip = self._created()
        late = self._new_late_guide()
        # Preparar el estado sin documentos financieros para probar el bloqueo.
        self.guide_a.sudo().write({'state': 'embarcada'})
        self.guide_b.sudo().write({'state': 'embarcada'})
        trip.with_user(self.driver).action_mark_embarked()
        with self.assertRaises(UserError):
            trip.with_user(self.driver).action_add_guides([late.id])
        with self.assertRaises(UserError):
            self.env['transcash.embarque'].with_user(self.driver).create_from_guides([late.id])
        self.assertFalse(late.embarque_id)

    def test_new_embark_allowed_only_after_trip_delivered(self):
        trip = self._created()
        later = self._new_late_guide()
        trip.sudo().write({'state': 'ruta'})
        with self.assertRaises(UserError):
            self.env['transcash.embarque'].with_user(self.driver).create_from_guides([later.id])
        # Simular entrega final; en operación real el estado es calculado al
        # recibir todas las guías, y no se manipula manualmente.
        trip.sudo().write({'state': 'entregado'})
        second = self.env['transcash.embarque'].with_user(self.driver).create_from_guides([later.id])
        self.assertNotEqual(second, trip)
        self.assertEqual(second.state, 'preparacion')

    def test_direct_sudo_create_still_enforces_one_active_trip(self):
        trip = self._created()
        with self.assertRaises(UserError):
            self.env['transcash.embarque'].sudo().create({
                'company_id': self.env.company.id,
                'chofer_usuario_id': self.driver.id,
                'proveedor_id': self.supplier.id,
                'placa': 'GYE-001',
            })
        self.assertEqual(trip.state, 'preparacion')
