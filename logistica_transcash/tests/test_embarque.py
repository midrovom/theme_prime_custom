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
