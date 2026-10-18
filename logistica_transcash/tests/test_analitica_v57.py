"""Pruebas funcionales para ejecutar en servidor Odoo 18 con --test-enable."""
from odoo.tests.common import TransactionCase
from odoo.exceptions import AccessError, UserError
from odoo import fields


class TestAnaliticaV57(TransactionCase):
    def setUp(self):
        super().setUp()
        self.supplier = self.env['res.partner'].create({'name':'Transporte Control V57','is_company':True})
        self.manager = self.env['res.users'].with_context(no_reset_password=True).create({
            'name':'Jefe de Logística V57','login':'logistica.v57@example.invalid',
            'groups_id':[(6,0,[self.env.ref('logistica_transcash.group_logistica_manager').id])],
        })
        self.approved_manager = self.env['res.users'].with_context(no_reset_password=True).create({
            'name':'Jefe con excepción V57','login':'excepcion.v57@example.invalid',
            'groups_id':[(6,0,[self.env.ref('logistica_transcash.group_logistica_manager').id,
                             self.env.ref('logistica_transcash.group_transcash_aprobacion_excepcional').id])],
        })
        self.analyst = self.env['res.users'].with_context(no_reset_password=True).create({
            'name':'Analista V57','login':'analista.v57@example.invalid',
            'groups_id':[(6,0,[self.env.ref('logistica_transcash.group_transcash_dashboard').id])],
        })
        self.driver = self.env['res.users'].with_context(no_reset_password=True).create({
            'name':'Conductor V57','login':'conductor.v57@example.invalid',
            'groups_id':[(6,0,[self.env.ref('base.group_portal').id,
                             self.env.ref('logistica_transcash.group_transcash_chofer').id])],
        })
        self.emb = self.env['transcash.embarque'].sudo().create({
            'name':'EMB/V57/001','company_id':self.env.company.id, 'chofer_usuario_id':self.driver.id,
            'proveedor_id':self.supplier.id,'state':'entregado','valor_acordado':150,
            'fecha_salida':'2026-10-15 12:00:00',
        })
        self.guia = self.env['transcash.guia'].sudo().create({
            'name':'G/V57/001','company_id':self.env.company.id,'embarque_id':self.emb.id,
            'proveedor_id':self.supplier.id, 'chofer_usuario_id':self.driver.id,
            'state':'revision', 'fecha_cierre_chofer':fields.Datetime.now(),
            'incidencia_estado':'abierta', 'resultado_recepcion':'pendiente',
            'destino':'Quito','destino_codigo':'UIO',
        })

    def test_normal_approval_with_open_incidence(self):
        self.emb.with_user(self.manager).action_approve_transport()
        self.assertEqual(self.emb.estado_aprobacion, 'aprobado')
        self.assertFalse(self.emb.aprobacion_excepcional)
        self.assertEqual(self.guia.incidencia_estado, 'abierta')
        self.assertEqual(self.guia.resultado_recepcion, 'pendiente')
        self.assertIn('publicado al proveedor', ' '.join(self.emb.message_ids.mapped('body')))
        with self.assertRaises(UserError):
            self.emb.with_user(self.manager).action_approve_transport()

    def test_cannot_override_not_delivered(self):
        self.emb.sudo().write({'state':'ruta'})
        with self.assertRaises(UserError):
            self.emb.with_user(self.approved_manager)._approve_exception('Mi decisión expresa exige cierre por chofer')

    def test_dashboard_separate_permission(self):
        with self.assertRaises(AccessError):
            self.env['transcash.dashboard.service'].with_user(self.manager).get_dashboard('mes','2026-10-01','2026-10-31')
        result = self.env['transcash.dashboard.service'].with_user(self.analyst).get_dashboard('mes','2026-10-01','2026-10-31')
        self.assertEqual(result['kpis']['viajes'],1)
        self.assertEqual(result['kpis']['guias'],1)
        self.assertTrue(any(x['nombre']=='UIO' for x in result['destinos']))

    def test_dashboard_rankings_reales_v511(self):
        """Regresión: grupos no vacíos (IDs y códigos) no deben causar KeyError.

        V5.10 sobrescribía la columna de ordenación con el ID de transportista,
        chofer o destino. Esto provocaba Server Error cuando había viajes.
        """
        data = self.env['transcash.dashboard.service'].with_user(self.analyst).get_dashboard(
            'dia', '2026-10-15', '2026-10-15')
        self.assertEqual(data['kpis']['viajes'], 1)
        self.assertEqual(data['transportistas'][0]['nombre'], self.supplier.display_name)
        self.assertEqual(data['choferes'][0]['nombre'], self.driver.display_name)
        self.assertEqual(data['destinos'][0]['clave'], 'UIO')
        self.assertEqual(data['tendencia'][0]['viajes'], 1)
