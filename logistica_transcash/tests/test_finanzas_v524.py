"""V5.24: tests para ejecutar en Odoo 18 (--test-enable -u logistica_transcash).

Valida bitácora de negociación, separación de funciones, factura, pagos
bancarios y recepción por proveedor, sin alterar el estado contable.
"""
import base64
from odoo.tests.common import TransactionCase
from odoo.exceptions import AccessError, UserError


class TestFinanzasV524(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.provider = cls.env['res.partner'].sudo().create({'name': 'Proveedor V524', 'is_company': True})
        cls.other_provider = cls.env['res.partner'].sudo().create({'name': 'Otro Proveedor V524', 'is_company': True})
        cls.partner_user = cls.env['res.partner'].sudo().create({'name': 'Portal V524', 'parent_id': cls.provider.id})
        cls.other_partner = cls.env['res.partner'].sudo().create({'name': 'Otro Portal V524', 'parent_id': cls.other_provider.id})
        cls.supplier = cls.env['res.users'].sudo().with_context(no_reset_password=True).create({
            'name': 'Transportista V524', 'login': 'v524.proveedor@example.invalid',
            'partner_id': cls.partner_user.id,
            'groups_id': [(6, 0, [cls.env.ref('base.group_portal').id,
                                    cls.env.ref('logistica_transcash.group_transcash_transportista').id])],
        })
        cls.other_supplier = cls.env['res.users'].sudo().with_context(no_reset_password=True).create({
            'name': 'Transportista Ajeno V524', 'login': 'v524.proveedor.ajeno@example.invalid',
            'partner_id': cls.other_partner.id,
            'groups_id': [(6, 0, [cls.env.ref('base.group_portal').id,
                                    cls.env.ref('logistica_transcash.group_transcash_transportista').id])],
        })
        cls.accountant = cls.env['res.users'].sudo().with_context(no_reset_password=True).create({
            'name': 'Contabilidad V524', 'login': 'v524.conta@example.invalid',
            'groups_id': [(6, 0, [cls.env.ref('logistica_transcash.group_transcash_contabilidad').id])],
        })
        cls.manager = cls.env['res.users'].sudo().with_context(no_reset_password=True).create({
            'name': 'Gerencia Logística V524', 'login': 'v524.manager@example.invalid',
            'groups_id': [(6, 0, [cls.env.ref('logistica_transcash.group_logistica_manager').id])],
        })
        cls.driver = cls.env['res.users'].sudo().with_context(no_reset_password=True).create({
            'name': 'Conductor V524', 'login': 'v524.driver@example.invalid',
            'groups_id': [(6, 0, [cls.env.ref('base.group_portal').id,
                                    cls.env.ref('logistica_transcash.group_transcash_chofer').id])],
        })
        cls.trip = cls.env['transcash.embarque'].sudo().create({
            'name': 'EMB-V524', 'company_id': cls.env.company.id,
            'chofer_usuario_id': cls.driver.id, 'proveedor_id': cls.provider.id,
            'placa': 'ABC-524', 'state': 'entregado', 'valor_acordado': 150.0,
        })
        cls.guide = cls.env['transcash.guia'].sudo().create({
            'name': 'G-V524', 'company_id': cls.env.company.id,
            'chofer_usuario_id': cls.driver.id, 'proveedor_id': cls.provider.id,
            'embarque_id': cls.trip.id, 'state': 'entregada',
            'aprobacion_global': 'aprobada', 'incidencia_estado': 'ninguna',
        })
        cls.pdf = base64.b64encode(b'%PDF-1.4\nprueba-v524').decode('ascii')

    def _invoice(self, rate=150.0):
        self.trip.with_user(self.manager).action_approve_transport()
        doc = self.env['transcash.pago.liquidacion'].with_user(self.supplier).create_supplier_liquidation([self.trip.id])
        doc.with_user(self.supplier).action_supplier_submit(
            'FACT-V524', '2026-10-15', rate, 0, self.pdf, 'factura.pdf')
        doc.with_user(self.accountant).action_accounting_approve()
        return doc

    def test_precio_negociado_y_chatter(self):
        wizard = self.env['transcash.tarifa.embarque.wizard'].with_user(self.manager).create({
            'embarque_id': self.trip.id, 'valor_acordado': 165.0,
            'motivo': 'Acuerdo único con el transportista'})
        wizard.action_confirm()
        self.assertEqual(self.trip.valor_acordado, 165.0)
        messages = ' '.join(self.trip.message_ids.mapped('body'))
        self.assertIn('150.00', messages)
        self.assertIn('165.00', messages)
        self.assertIn('Acuerdo único', messages)
        with self.assertRaises(AccessError):
            self.env['transcash.tarifa.embarque.wizard'].with_user(self.accountant).create({
                'embarque_id': self.trip.id, 'valor_acordado': 100.0,
                'motivo': 'Sin permiso'})

    def test_pago_total_sigue_pagada_si_proveedor_objeta(self):
        doc = self._invoice()
        self.assertEqual(doc.confirmacion_pagos, 'sin_pagos')
        doc.with_user(self.accountant).action_register_payment(
            150.0, '2026-10-15', 'BCO-V524', 'transferencia', self.pdf, 'pago.pdf')
        self.assertEqual(doc.estado, 'pagada')
        self.assertEqual(doc.confirmacion_pagos, 'pendiente')
        payment = doc.pago_ids[0]
        with self.assertRaises(AccessError):
            payment.with_user(self.other_supplier).action_supplier_receipt('confirmada')
        with self.assertRaises(AccessError):
            payment.with_user(self.accountant).action_supplier_receipt('confirmada')
        with self.assertRaises(UserError):
            payment.with_user(self.supplier).action_supplier_receipt('disputa', 'no')
        payment.with_user(self.supplier).action_supplier_receipt('disputa', 'No figura el depósito en la cuenta indicada')
        self.assertEqual(doc.estado, 'pagada')
        self.assertEqual(self.trip.estado_financiero, 'pagada')
        self.assertEqual(doc.confirmacion_pagos, 'disputa')
        self.assertEqual(payment.recepcion_por_id, self.supplier)
        self.assertTrue(payment.recepcion_fecha)
        with self.assertRaises(UserError):
            payment.with_user(self.supplier).action_supplier_receipt('confirmada')

    def test_confirmacion_parcial_de_transferencias(self):
        doc = self._invoice()
        doc.with_user(self.accountant).action_register_payment(
            50.0, '2026-10-15', 'BCO-1-V524', 'transferencia', self.pdf, 'p1.pdf')
        doc.with_user(self.accountant).action_register_payment(
            100.0, '2026-10-15', 'BCO-2-V524', 'transferencia', self.pdf, 'p2.pdf')
        self.assertEqual(doc.estado, 'pagada')
        payments = doc.pago_ids.sorted('id')
        payments[0].with_user(self.supplier).action_supplier_receipt('confirmada', 'Revisado en banco')
        self.assertEqual(doc.confirmacion_pagos, 'parcial')
        payments[1].with_user(self.supplier).action_supplier_receipt('confirmada', 'Revisado')
        self.assertEqual(doc.confirmacion_pagos, 'confirmada')
        self.assertEqual(doc.estado, 'pagada')
