"""V5.15: cobertura de selector y autorizaciones de ruta (Odoo 18)."""
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError


class TestSelectorV515(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.manager = cls.env.ref('base.user_admin')
        cls.manager.sudo().write({'groups_id': [(4, cls.env.ref('logistica_transcash.group_logistica_manager').id)]})
        cls.driver = cls.env['res.users'].sudo().create({
            'name': 'V515 Chofer Uno', 'login': 'v515-chofer1@example.invalid',
            'groups_id': [(6, 0, [cls.env.ref('base.group_portal').id,
                                   cls.env.ref('logistica_transcash.group_transcash_chofer').id])]})
        cls.other_driver = cls.env['res.users'].sudo().create({
            'name': 'V515 Chofer Dos', 'login': 'v515-chofer2@example.invalid',
            'groups_id': [(6, 0, [cls.env.ref('base.group_portal').id,
                                   cls.env.ref('logistica_transcash.group_transcash_chofer').id])]})
        cls.carrier = cls.env['res.partner'].create({'name': 'Transportista V515'})
        cls.other_carrier = cls.env['res.partner'].create({'name': 'Transportista alternativo V515'})
        cls.client = cls.env['res.partner'].create({'name': 'Cliente V515'})
        cls.dest = cls.env['transcash.destino'].with_user(cls.manager).create({
            'name': 'Quito V515', 'ciudad': 'Quito',
            'codigo': 'EC-UIO-V515', 'company_id': cls.env.company.id})
        cls.other_dest = cls.env['transcash.destino'].with_user(cls.manager).create({
            'name': 'Cuenca V515', 'ciudad': 'Cuenca',
            'codigo': 'EC-CUE-V515', 'company_id': cls.env.company.id})
        cls.env['transcash.tarifa.traslado'].with_user(cls.manager).create({
            'company_id': cls.env.company.id, 'destino_id': cls.dest.id,
            'tipo_vehiculo': 'camion', 'precio': 220})

    def _guide(self, code, **kw):
        v = {'company_id': self.env.company.id, 'name': code,
             'destinatario_id': self.client.id, 'destino_id': self.dest.id,
             'destino_codigo': self.dest.codigo,
             'chofer_usuario_id': self.driver.id, 'proveedor_id': self.carrier.id}
        v.update(kw)
        return self.env['transcash.guia'].sudo().create(v)

    def _route(self):
        return self.env['transcash.hoja.ruta'].with_user(self.manager).create({
            'company_id': self.env.company.id, 'destino_id': self.dest.id,
            'chofer_usuario_id': self.driver.id, 'proveedor_id': self.carrier.id,
            'tipo_vehiculo': 'camion', 'placa': 'GAA-V515'})

    def _wizard(self, route):
        action = route.with_user(self.manager).action_open_guide_selector()
        return self.env['transcash.seleccionar.guias.ruta.wizard'].with_user(self.manager).browse(action['res_id'])

    def test_guia_erp_con_nombre_de_ciudad_permite_agregar_y_confirmar(self):
        g = self._guide('V515-LEGACY', destino_id=False, destino_codigo=False,
                        destino='QUITO', destino_ciudad='quito')
        r = self._route()
        wizard = self._wizard(r)
        line = wizard.linea_ids.filtered(lambda l: l.guia_id == g)
        self.assertTrue(line)
        self.assertTrue(line.disponible)
        line.write({'seleccionada': True})
        wizard.action_aplicar()
        self.assertEqual(r.seleccion_guia_ids, g)
        r.with_user(self.manager).action_confirm_route()
        self.assertEqual(g.hoja_ruta_id, r)
        self.assertEqual(g.destino_id, self.dest)

    def test_cambio_de_chofer_y_transportista_auditado(self):
        g = self._guide('V515-REASIGNADO', chofer_usuario_id=self.other_driver.id,
                        proveedor_id=self.other_carrier.id)
        r = self._route()
        wizard = self._wizard(r)
        line = wizard.linea_ids.filtered(lambda l: l.guia_id == g)
        self.assertTrue(line.disponible)
        self.assertTrue(line.requiere_reasignacion)
        line.write({'seleccionada': True})
        with self.assertRaisesRegex(UserError, 'autorización'):
            wizard.action_aplicar()
        wizard.write({'permitir_reasignar': True})
        wizard.action_aplicar()
        self.assertTrue(r.reasignacion_autorizada)
        r.with_user(self.manager).action_confirm_route()
        self.assertEqual(g.chofer_usuario_id, self.driver)
        self.assertEqual(g.proveedor_id, self.carrier)
        self.assertTrue(g.evento_ids.filtered(lambda e: 'Reasignación autorizada' in e.accion))

    def test_guia_de_otro_destino_bloqueada_aunque_autorice(self):
        g = self._guide('V515-OTRO-DEST', destino_id=self.other_dest.id,
                        destino_codigo=self.other_dest.codigo)
        r = self._route()
        wizard = self._wizard(r)
        search = wizard.abrir_para_ruta(r, buscar_numero=g.name)
        wiz = self.env['transcash.seleccionar.guias.ruta.wizard'].browse(search['res_id'])
        row = wiz.linea_ids.filtered(lambda l: l.guia_id == g)
        self.assertTrue(row)
        self.assertFalse(row.disponible)
        self.assertIn('destino', row.motivo)
        row.sudo().write({'seleccionada': True})
        wiz.write({'permitir_reasignar': True})
        with self.assertRaisesRegex(UserError, 'Bloqueada'):
            wiz.action_aplicar()
        self.assertFalse(r.seleccion_guia_ids)

    def test_confirmar_sin_autorizacion_no_acepta_cambio_por_rpc(self):
        g = self._guide('V515-BLOQUEO-RPC', chofer_usuario_id=self.other_driver.id)
        r = self._route()
        r.sudo().write({'seleccion_guia_ids': [(6, 0, [g.id])]})
        with self.assertRaisesRegex(UserError, 'autorice expresamente'):
            r.with_user(self.manager).action_confirm_route()
        self.assertFalse(g.hoja_ruta_id)

    def test_guia_registrada_ocupada_no_se_duplica(self):
        g = self._guide('V515-OCUPADA')
        old = self._route()
        old.sudo().write({'seleccion_guia_ids': [(6, 0, [g.id])]})
        old.with_user(self.manager).action_confirm_route()
        next_route = self._route()
        wiz = self._wizard(next_route)
        line = wiz.abrir_para_ruta(next_route, buscar_numero=g.name)
        matching = self.env['transcash.seleccionar.guias.ruta.wizard'].browse(line['res_id'])
        r = matching.linea_ids.filtered(lambda row: row.guia_id == g)
        self.assertTrue(r)
        self.assertFalse(r.disponible)

    def test_abrir_y_guardar_varias_guias_sin_perder_seleccion(self):
        g1 = self._guide('V515-01')
        g2 = self._guide('V515-02')
        route = self._route()
        wizard = self._wizard(route)
        wizard.linea_ids.filtered(lambda l: l.guia_id == g1).write({'seleccionada': True})
        action = wizard.abrir_para_ruta(route, buscar_numero='V515-02', ids_ya_marcados=[g1.id, g2.id])
        reloaded = self.env['transcash.seleccionar.guias.ruta.wizard'].browse(action['res_id'])
        self.assertEqual(set(reloaded.linea_ids.filtered('seleccionada').mapped('guia_id').ids), {g1.id, g2.id})
        reloaded.action_aplicar()
        self.assertEqual(set(route.seleccion_guia_ids.ids), {g1.id, g2.id})
