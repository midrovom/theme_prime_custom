"""Galería de carga, descarga y firma, y aislamiento de evidencias del destinatario.

Ejecutar con --test-enable sobre una base de pruebas Odoo 18.
"""
import base64
from odoo.tests.common import TransactionCase
from odoo.exceptions import AccessError
from ..controllers.evidence_hub import gallery_for_trip, gallery_for_guide


class TestEvidenceHubV520(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.driver = cls.env['res.users'].sudo().create({
            'name':'Chofer visor V520', 'login':'v520-driver@example.invalid',
            'groups_id':[(6,0,[cls.env.ref('base.group_portal').id,
                               cls.env.ref('logistica_transcash.group_transcash_chofer').id])],
        })
        cls.carrier = cls.env['res.partner'].sudo().create({'name':'Transporte V520'})
        cls.client1 = cls.env['res.partner'].sudo().create({'name':'Destinatario uno 520'})
        cls.client2 = cls.env['res.partner'].sudo().create({'name':'Destinatario dos 520'})
        cls.client_user = cls.env['res.users'].sudo().create({
            'name':'Portal destinatario uno 520','login':'v520-client@example.invalid',
            'partner_id':cls.client1.id,
            'groups_id':[(6,0,[cls.env.ref('base.group_portal').id,
                               cls.env.ref('logistica_transcash.group_transcash_cliente').id])],
        })

    def _trip(self):
        trip = self.env['transcash.embarque'].sudo().create({
            'name':'TEST-GAL-520','company_id':self.env.company.id,
            'chofer_usuario_id':self.driver.id,
            'proveedor_id':self.carrier.id,'placa':'GUI-520',
            'valor_acordado':999.00,
        })
        a = self.env['transcash.guia'].sudo().create({
            'name':'GAL-520-A','destinatario_id':self.client1.id,
            'company_id':self.env.company.id,'embarque_id':trip.id,
            'proveedor_id':self.carrier.id,'chofer_usuario_id':self.driver.id,
        })
        b = self.env['transcash.guia'].sudo().create({
            'name':'GAL-520-B','destinatario_id':self.client2.id,
            'company_id':self.env.company.id,'embarque_id':trip.id,
            'proveedor_id':self.carrier.id,'chofer_usuario_id':self.driver.id,
        })
        picture = base64.b64encode(b'\xff\xd8\xff\xe0' + b'\x00'*50).decode('ascii')
        for guide in (a,b):
            self.env['transcash.evidencia'].sudo().create({
                'guia_id':guide.id,'tipo':'llegada','observacion':'Prueba de recepción',
                'archivo':picture,'archivo_mime':'image/jpeg',
                'archivo_nombre':'descarga-%s.jpg'%guide.name,
            })
        a.sudo().write({
            'firma_receptor':base64.b64encode(b'\x89PNG\r\n\x1a\n'+b'\x00'*50).decode('ascii'),
            'firma_receptor_fecha':'2026-10-18 12:00:00',
            'persona_presente_chofer':'Firma Cliente Uno',
        })
        return trip, a, b

    def test_trip_gallery_groups_evidence_without_price(self):
        trip, a, b = self._trip()
        result = gallery_for_trip(trip)
        self.assertEqual(len(result['gallery_descarga']), 2)
        self.assertEqual(len(result['gallery_firmas']), 1)
        self.assertEqual(result['gallery_count'], 3)
        self.assertTrue(all(row['url'].startswith('/transcash/') for row in result['gallery_descarga']))
        self.assertNotIn('valor_acordado',result)
        self.assertNotIn('tarifa_referencial_total',result)

    def test_customer_gallery_shows_own_guide_only(self):
        trip, a, b = self._trip()
        data = gallery_for_guide(a, is_recipient_only=True)
        ids = ' '.join(x['url'] for x in data['gallery_descarga'])
        self.assertIn('/transcash/evidencia/%s/archivo' % a.evidencia_ids[0].id, ids)
        self.assertNotIn('/transcash/evidencia/%s/archivo' % b.evidencia_ids[0].id, ids)
        self.assertEqual(len(data['gallery_firmas']),1)
        self.assertFalse(data['gallery_carga'])
        self.assertTrue(a._is_recipient(self.client_user))
        self.assertFalse(b._is_recipient(self.client_user))
        with self.assertRaises(AccessError):
            a.with_user(self.client_user)._check_internal_gallery_access()
