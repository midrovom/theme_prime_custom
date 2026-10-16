"""V5.14: selección real por casillas, persistencia y rechazo de guías ajenas.

Ejecutar en Odoo 18 con --test-enable (sin necesidad de navegador).
"""
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError


class TestSelectorRealV514(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.manager = cls.env.ref('base.user_admin')
        cls.manager.sudo().write({'groups_id': [(4, cls.env.ref(
            'logistica_transcash.group_logistica_manager').id)]})
        cls.driver = cls.env['res.users'].sudo().create({
            'name': 'Chofer V514', 'login': 'tc-v514-chofer@example.invalid',
            'groups_id': [(6, 0, [cls.env.ref('base.group_portal').id,
                                   cls.env.ref('logistica_transcash.group_transcash_chofer').id])],
        })
        cls.carrier = cls.env['res.partner'].create({'name': 'Transportista V514'})
        cls.other_carrier = cls.env['res.partner'].create({'name': 'Otro Transportista V514'})
        cls.customer = cls.env['res.partner'].create({'name': 'Destinatario V514'})
        cls.destination = cls.env['transcash.destino'].with_user(cls.manager).create({
            'name': 'Destino V514', 'codigo': 'EC-V514', 'company_id': cls.env.company.id,
        })

    def _guide(self, code, **overrides):
        vals = {
            'name': code, 'company_id': self.env.company.id,
            'destino_id': self.destination.id, 'destino_codigo': self.destination.codigo,
            'chofer_usuario_id': self.driver.id,
            'proveedor_id': self.carrier.id, 'destinatario_id': self.customer.id,
        }
        vals.update(overrides)
        return self.env['transcash.guia'].sudo().create(vals)

    def _route(self):
        return self.env['transcash.hoja.ruta'].with_user(self.manager).create({
            'company_id': self.env.company.id,
            'chofer_usuario_id': self.driver.id,
            'proveedor_id': self.carrier.id,
            'placa': 'ABC-V514', 'tipo_vehiculo': 'camion',
            'destino_id': self.destination.id,
        })

    def _open(self, ruta):
        action = ruta.action_open_guide_selector()
        self.assertEqual(action['target'], 'new')
        return self.env['transcash.seleccionar.guias.ruta.wizard'].with_user(
            self.manager).browse(action['res_id'])

    def test_puede_agregar_y_quitar_sin_buscar_etiquetas(self):
        g1 = self._guide('GUIA-V514-01')
        g2 = self._guide('GUIA-V514-02')
        ruta = self._route()
        wiz = self._open(ruta)
        self.assertEqual(wiz.total_disponibles, 2)
        self.assertEqual(len(wiz.linea_ids), 2)
        wiz.linea_ids.filtered(lambda l: l.guia_id == g1).write({'seleccionada': True})
        wiz.linea_ids.filtered(lambda l: l.guia_id == g2).write({'seleccionada': True})
        wiz.action_aplicar()
        self.assertEqual(set(ruta.seleccion_guia_ids.ids), {g1.id, g2.id})
        self.assertEqual(ruta.cantidad_guias_seleccionadas, 2)
        wiz2 = self._open(ruta)
        wiz2.linea_ids.filtered(lambda l: l.guia_id == g1).write({'seleccionada': False})
        wiz2.action_aplicar()
        self.assertEqual(ruta.seleccion_guia_ids, g2)

    def test_diferencia_transportista_requiere_aprobacion_explicita(self):
        other = self._guide('GUIA-V514-BLOCK', proveedor_id=self.other_carrier.id)
        ruta = self._route()
        wiz = self._open(ruta)
        line = wiz.linea_ids.filtered(lambda l: l.guia_id == other)
        self.assertTrue(line)
        self.assertTrue(line.disponible)
        self.assertTrue(line.requiere_reasignacion)
        self.assertIn('autorización', line.motivo)
        line.write({'seleccionada': True})
        with self.assertRaisesRegex(UserError, 'autorización de reasignación'):
            wiz.action_aplicar()
        self.assertFalse(ruta.seleccion_guia_ids)
        wiz.write({'permitir_reasignar': True})
        wiz.action_aplicar()
        self.assertEqual(ruta.seleccion_guia_ids, other)
        self.assertTrue(ruta.reasignacion_autorizada)

    def test_dos_ventanas_no_pisan_la_seleccion_entre_si(self):
        g1 = self._guide('GUIA-V514-WIN1')
        g2 = self._guide('GUIA-V514-WIN2')
        ruta = self._route()
        first = self._open(ruta)
        second = self._open(ruta)
        first.linea_ids.filtered(lambda l: l.guia_id == g1).write({'seleccionada': True})
        first.action_aplicar()
        second.linea_ids.filtered(lambda l: l.guia_id == g2).write({'seleccionada': True})
        with self.assertRaisesRegex(UserError, 'Otro operador'):
            second.action_aplicar()
        self.assertEqual(ruta.seleccion_guia_ids, g1)
