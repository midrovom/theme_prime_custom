"""Destinos normalizados, tarifas y guías de API V5.12. Ejecutar en Odoo 18."""
from odoo.tests.common import TransactionCase
from odoo.exceptions import AccessError, UserError, ValidationError


class TestDestinos(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.manager = cls.env.ref('base.user_admin')
        cls.manager.sudo().write({'groups_id': [
            (4, cls.env.ref('logistica_transcash.group_logistica_manager').id)]})
        cls.destino = cls.env['transcash.destino'].with_user(cls.manager).create({
            'company_id': cls.env.company.id, 'codigo': ' ec-uio ',
            'name': 'Quito', 'ciudad': 'Quito', 'provincia': 'Pichincha',
        })

    def test_crea_tarifa_y_ruta_solo_seleccionando_destino(self):
        tarifa = self.env['transcash.tarifa.traslado'].with_user(self.manager).create({
            'company_id': self.env.company.id, 'tipo_vehiculo': 'camion',
            'destino_id': self.destino.id, 'precio': 180.0,
        })
        self.assertEqual(tarifa.destino_codigo, 'EC-UIO')
        self.assertEqual(tarifa.destino_nombre, 'Quito')
        with self.assertRaises(ValidationError):
            self.env['transcash.tarifa.traslado'].with_user(self.manager).create({
                'company_id': self.env.company.id, 'tipo_vehiculo': 'mula',
                'destino_codigo': 'OTRO-DESTINO', 'destino_nombre': 'Otro', 'precio': 120,
            })

    def test_api_homologa_destino_con_codigo_estable(self):
        guias = self.env['transcash.guia'].sudo()
        payload = {'guias': [
            {'id_externo': 'TCV512-001', 'numero_guia': 'TCV512-001',
             'destino_codigo': 'EC-UIO', 'destino_ciudad': 'Quito cambiado',
             'destino_provincia': 'Pichincha'},
        ]}
        before = self.env['transcash.destino'].sudo().search_count([
            ('company_id', '=', self.env.company.id), ('codigo', '=', 'EC-UIO')])
        r1 = guias.sync_payload(payload)
        r2 = guias.sync_payload(payload)
        self.assertEqual(r1['creadas'], 1)
        self.assertEqual(r2['actualizadas'], 1)
        self.assertEqual(r1['errores'], [])
        self.assertEqual(before, 1)
        self.assertEqual(self.env['transcash.destino'].sudo().search_count([
            ('company_id', '=', self.env.company.id), ('codigo', '=', 'EC-UIO')]), 1)
        guia = guias.search([('external_id_erp', '=', 'TCV512-001')], limit=1)
        self.assertEqual(guia.destino_id.id, self.destino.id)
        self.assertEqual(self.destino.name, 'Quito')  # Reenvíos no renombran maestro

    def test_api_crea_destino_nuevo_en_el_mismo_endpoint(self):
        vals = self.env['transcash.guia'].sudo()._external_values({
            'id_externo': 'TCV512-002', 'numero_guia': 'TCV512-002',
            'destino_codigo': 'EC-CUE', 'destino_ciudad': 'Cuenca',
            'destino_provincia': 'Azuay',
        })
        new = self.env['transcash.destino'].sudo().browse(vals['destino_id'])
        self.assertEqual(new.codigo, 'EC-CUE')
        self.assertEqual(new.name, 'Cuenca')
        self.assertEqual(new.fuente, 'erp')

    def test_no_se_puede_cambiar_codigo_en_uso(self):
        self.env['transcash.tarifa.traslado'].with_user(self.manager).create({
            'company_id': self.env.company.id, 'tipo_vehiculo': 'camion',
            'destino_id': self.destino.id, 'precio': 180.0,
        })
        with self.assertRaises(UserError):
            self.destino.with_user(self.manager).write({'codigo': 'EC-UY2'})

    def test_destino_invalido_rechazado(self):
        with self.assertRaises(ValidationError):
            self.env['transcash.destino'].with_user(self.manager).create({
                'name': 'Mal', 'codigo': 'a b c'})
