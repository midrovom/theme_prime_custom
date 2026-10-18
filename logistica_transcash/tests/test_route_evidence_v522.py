"""Regresión V5.22: evidencias por ruta y cierre automático con última ruta.

Ejecutar en una base de pruebas Odoo 18 con --test-enable.
"""
import base64
from odoo import fields
from odoo.tests.common import TransactionCase
from ..controllers.evidence_hub import gallery_for_trip, gallery_for_guide


class TestRutaEvidenceV522(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.driver = cls.env['res.users'].sudo().create({
            'name':'Chofer cierre V522','login':'v522-driver@example.invalid',
            'groups_id':[(6,0,[cls.env.ref('base.group_portal').id,
                               cls.env.ref('logistica_transcash.group_transcash_chofer').id])],
        })
        cls.carrier = cls.env['res.partner'].sudo().create({'name':'Transportista V522'})
        cls.client_a = cls.env['res.partner'].sudo().create({'name':'Cliente V522 A'})
        cls.client_b = cls.env['res.partner'].sudo().create({'name':'Cliente V522 B'})
        cls.client_user = cls.env['res.users'].sudo().create({
            'name':'Cliente portal V522','login':'v522-client@example.invalid',
            'partner_id':cls.client_a.id,
            'groups_id':[(6,0,[cls.env.ref('base.group_portal').id,
                               cls.env.ref('logistica_transcash.group_transcash_cliente').id])],
        })
        cls.dest_a = cls.env['transcash.destino'].sudo().create({
            'codigo':'D-522-A','name':'Destino V522 A', 'company_id':cls.env.company.id})
        cls.dest_b = cls.env['transcash.destino'].sudo().create({
            'codigo':'D-522-B','name':'Destino V522 B', 'company_id':cls.env.company.id})

    def _trip_two_routes(self):
        # Se arma como un único viaje, sin tarifa por cada hoja de ruta.
        emb = self.env['transcash.embarque'].sudo().create({
            'company_id':self.env.company.id, 'chofer_usuario_id':self.driver.id,
            'proveedor_id':self.carrier.id,'placa':'ABC-522', 'state':'preparacion',
        })
        routes = self.env['transcash.hoja.ruta'].sudo()
        for dest in (self.dest_a, self.dest_b):
            routes |= self.env['transcash.hoja.ruta'].sudo().create({
                'company_id':self.env.company.id,'chofer_usuario_id':self.driver.id,
                'proveedor_id':self.carrier.id,'placa':'ABC-522','tipo_vehiculo':'camion',
                'destino_id':dest.id,'embarque_id':emb.id,'state':'planificada',
            })
        guides = self.env['transcash.guia'].sudo()
        for idx, route in enumerate((routes[0],routes[0],routes[1])):
            guides |= self.env['transcash.guia'].sudo().create({
                'name':'V522-G-%d' % idx,'company_id':self.env.company.id,
                'destinatario_id':self.client_a.id if idx != 1 else self.client_b.id,
                'chofer_usuario_id':self.driver.id,'proveedor_id':self.carrier.id,
                'embarque_id':emb.id,'hoja_ruta_id':route.id,
                'state':'ruta',
            })
        emb.sudo().write({'state':'ruta'})
        return emb, routes, guides

    def test_gallery_uses_route_sections_without_crossing_guides(self):
        emb, routes, guides = self._trip_two_routes()
        photo = base64.b64encode(b'\xff\xd8\xff\xe0' + b'\x00'*50).decode('ascii')
        first = self.env['transcash.evidencia'].sudo().create({
            'guia_id':guides[0].id,'tipo':'llegada','archivo':photo,
            'archivo_mime':'image/jpeg','archivo_nombre':'ruta-A.jpg',
        })
        second = self.env['transcash.evidencia'].sudo().create({
            'guia_id':guides[2].id,'tipo':'llegada','archivo':photo,
            'archivo_mime':'image/jpeg','archivo_nombre':'ruta-B.jpg',
        })
        guides[0].sudo().write({'firma_receptor':base64.b64encode(b'\x89PNG\r\n\x1a\n'+b'x'*150).decode('ascii'),
                                'firma_receptor_fecha':fields.Datetime.now()})
        result = gallery_for_trip(emb)
        self.assertEqual(len(result['gallery_routes']), 2)
        one, two = result['gallery_routes']
        self.assertEqual(one['name'],routes[0].name)
        self.assertEqual(two['name'],routes[1].name)
        self.assertIn('/transcash/evidencia/%d/archivo' % first.id,
                      [m['url'] for m in one['descarga']])
        self.assertNotIn('/transcash/evidencia/%d/archivo' % second.id,
                         [m['url'] for m in one['descarga']])
        self.assertEqual(len(one['firmas']),1)
        self.assertEqual(len(two['firmas']),0)
        self.assertEqual(result['gallery_count'],3)
        self.assertNotIn('valor_acordado', result)
        recipient = gallery_for_guide(guides[0], is_recipient_only=True)
        self.assertEqual(len(recipient['gallery_routes']),1)
        self.assertEqual(recipient['gallery_routes'][0]['name'],'Mi guía')
        self.assertNotIn(routes[0].name, str(recipient['gallery_routes']))
        self.assertFalse(recipient['gallery_carga'])
        self.assertEqual(len(recipient['gallery_descarga']),1)
        self.assertEqual(len(recipient['gallery_firmas']),1)

    def test_closing_last_guide_of_last_route_closes_trip(self):
        emb, routes, guides = self._trip_two_routes()
        stamp = fields.Datetime.now()
        guides[0].sudo().write({'state':'revision','fecha_cierre_chofer':stamp})
        emb._refresh_delivered_state()
        self.assertEqual(emb.state,'ruta')
        self.assertEqual(routes[0].estado_entrega,'parcial')
        self.assertFalse(routes[0].fecha_cierre_operativo)
        guides[1].sudo().write({'state':'revision','fecha_cierre_chofer':stamp})
        emb._refresh_delivered_state()
        self.assertEqual(routes[0].estado_entrega,'completa')
        self.assertTrue(routes[0].fecha_cierre_operativo)
        self.assertEqual(emb.state,'ruta')
        self.assertFalse(routes[1].fecha_cierre_operativo)
        guides[2].sudo().write({'state':'revision','fecha_cierre_chofer':stamp})
        emb._refresh_delivered_state()
        self.assertTrue(routes[1].fecha_cierre_operativo)
        self.assertEqual(emb.state,'entregado')
        self.assertTrue(emb.fecha_entrega)
        self.assertTrue(all(g.state=='revision' for g in guides))  # cliente revisa después
        fecha_viaje = emb.fecha_entrega
        emb._refresh_delivered_state()
        self.assertEqual(emb.fecha_entrega, fecha_viaje)  # cierre idempotente

    def test_empty_route_never_closes_trip(self):
        emb, routes, guides = self._trip_two_routes()
        guides[2].sudo().write({'hoja_ruta_id':False})
        for g in guides:
            g.sudo().write({'state':'revision','fecha_cierre_chofer':fields.Datetime.now()})
        emb._refresh_delivered_state()
        self.assertEqual(emb.state,'ruta')
        self.assertFalse(routes[1].fecha_cierre_operativo)
