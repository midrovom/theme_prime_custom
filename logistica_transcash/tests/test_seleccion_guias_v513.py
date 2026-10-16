"""V5.13: selection of ERP guides by carrier, driver and normalized destination.

Run with Odoo 18's test runner; these are not stand-alone unittest tests.
"""
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError


class TestSeleccionGuiasRuta(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.manager = cls.env.ref('base.user_admin')
        cls.manager.sudo().write({'groups_id': [(4, cls.env.ref('logistica_transcash.group_logistica_manager').id)]})
        cls.driver = cls.env['res.users'].sudo().create({
            'name': 'Chofer V513 uno', 'login': 'tc-v513-driver-a@example.invalid',
            'groups_id': [(6, 0, [cls.env.ref('base.group_portal').id,
                                    cls.env.ref('logistica_transcash.group_transcash_chofer').id])],
        })
        cls.driver_other = cls.env['res.users'].sudo().create({
            'name': 'Chofer V513 otro', 'login': 'tc-v513-driver-b@example.invalid',
            'groups_id': [(6, 0, [cls.env.ref('base.group_portal').id,
                                    cls.env.ref('logistica_transcash.group_transcash_chofer').id])],
        })
        cls.vendor = cls.env['res.partner'].create({'name': 'Transporte V513 A'})
        cls.vendor_other = cls.env['res.partner'].create({'name': 'Transporte V513 B'})
        cls.customer = cls.env['res.partner'].create({'name': 'Destinatario V513'})
        cls.destino = cls.env['transcash.destino'].with_user(cls.manager).create({
            'name': 'Quito V513', 'codigo': 'EC-UIO-V513', 'company_id': cls.env.company.id,
        })
        cls.destino_other = cls.env['transcash.destino'].with_user(cls.manager).create({
            'name': 'Cuenca V513', 'codigo': 'EC-CUE-V513', 'company_id': cls.env.company.id,
        })
        cls.env['transcash.tarifa.traslado'].with_user(cls.manager).create({
            'tipo_vehiculo': 'camion', 'destino_id': cls.destino.id,
            'precio': 150.0, 'company_id': cls.env.company.id,
        })

    def _guide(self, suffix, **vals):
        return self.env['transcash.guia'].sudo().create(dict({
            'name': 'V513-G-' + suffix, 'company_id': self.env.company.id,
            'chofer_usuario_id': self.driver.id, 'proveedor_id': self.vendor.id,
            'destino_id': self.destino.id, 'destino_codigo': self.destino.codigo,
            'destinatario_id': self.customer.id,
        }, **vals))

    def _route(self, guide_ids=None):
        return self.env['transcash.hoja.ruta'].with_user(self.manager).create({
            'company_id': self.env.company.id,
            'chofer_usuario_id': self.driver.id,
            'proveedor_id': self.vendor.id,
            'placa': 'ABC-513', 'tipo_vehiculo': 'camion',
            'destino_id': self.destino.id,
            'seleccion_guia_ids': [(6, 0, guide_ids or [])],
        })

    def test_selector_resuelve_maestro_y_guias_historicas(self):
        """Regression: old domain on destino_codigo hid a valid guide by M2O."""
        linked_without_code = self._guide('01', destino_codigo=False)
        legacy_by_code = self._guide('02', destino_id=False)
        wrong_destination = self._guide('03', destino_id=self.destino_other.id,
                                        destino_codigo=self.destino_other.codigo)
        wrong_driver = self._guide('04', chofer_usuario_id=self.driver_other.id)
        wrong_carrier = self._guide('05', proveedor_id=self.vendor_other.id)
        unassigned = self._guide('06', chofer_usuario_id=False, proveedor_id=False)
        route = self._route()
        eligible = self.env['transcash.guia'].search(route._domain_guias_elegibles())
        self.assertIn(linked_without_code, eligible)
        self.assertIn(legacy_by_code, eligible)
        self.assertIn(unassigned, eligible)
        self.assertNotIn(wrong_destination, eligible)
        # V5.15: Logística puede elegir otro chofer o transportista solo si
        # acepta expresamente y deja trazabilidad de la reasignación.
        self.assertIn(wrong_driver, eligible)
        self.assertIn(wrong_carrier, eligible)
        self.assertFalse(route._es_guia_elegible(wrong_driver))
        self.assertFalse(route._es_guia_elegible(wrong_carrier))
        self.assertTrue(route._es_guia_elegible(wrong_driver, permitir_reasignacion=True))
        self.assertEqual(route.guias_disponibles, 5)
        self.assertEqual(route.guias_pendientes_destino, 5)

    def test_confirma_guias_del_erp_y_completa_asignaciones_vacias(self):
        linked_without_code = self._guide('07', destino_codigo=False)
        unassigned = self._guide('08', chofer_usuario_id=False, proveedor_id=False)
        ruta = self._route([linked_without_code.id, unassigned.id])
        ruta.action_confirm_route()
        self.assertEqual(ruta.state, 'planificada')
        self.assertEqual(ruta.tarifa_referencial, 150.0)
        self.assertEqual(linked_without_code.hoja_ruta_id, ruta)
        self.assertEqual(unassigned.chofer_usuario_id, self.driver)
        self.assertEqual(unassigned.proveedor_id, self.vendor)

    def test_no_reasigna_chofer_o_transportista_distintos_por_rpc(self):
        other_driver = self._guide('09', chofer_usuario_id=self.driver_other.id)
        ruta = self._route([other_driver.id])
        with self.assertRaisesRegex(UserError, 'chofer'):
            ruta.action_confirm_route()
        self.assertFalse(other_driver.hoja_ruta_id)
        self.assertEqual(other_driver.chofer_usuario_id, self.driver_other)
        other_vendor = self._guide('10', proveedor_id=self.vendor_other.id)
        ruta2 = self._route([other_vendor.id])
        with self.assertRaisesRegex(UserError, 'transportista'):
            ruta2.action_confirm_route()
        self.assertFalse(other_vendor.hoja_ruta_id)
        self.assertEqual(other_vendor.proveedor_id, self.vendor_other)

    def test_no_aparece_una_guia_ya_planificada(self):
        guide = self._guide('11')
        ruta = self._route([guide.id])
        ruta.action_confirm_route()
        nueva_ruta = self._route()
        eligible = self.env['transcash.guia'].search(nueva_ruta._domain_guias_elegibles())
        self.assertNotIn(guide, eligible)
        self.assertEqual(nueva_ruta.guias_disponibles, 0)

    def test_onchange_descarta_seleccion_no_compatible(self):
        guide = self._guide('12')
        record = self.env['transcash.hoja.ruta'].new({
            'company_id': self.env.company.id,
            'destino_id': self.destino.id,
            'chofer_usuario_id': self.driver.id,
            'proveedor_id': self.vendor_other.id,
            'seleccion_guia_ids': [(6, 0, [guide.id])],
        })
        result = record._onchange_filtros_guias()
        # V5.15: se conserva la selección si solo cambia el transportista,
        # porque requiere autorización explícita antes de confirmar.
        self.assertEqual(record.seleccion_guia_ids, guide)
        self.assertFalse(result)
        self.assertTrue(record._motivos_reasignacion(guide))
