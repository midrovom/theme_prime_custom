"""Pruebas a ejecutar DENTRO de Odoo 18: --test-enable / -u logistica_transcash.
Valida roles, liquidación única por embarque, factura, conciliación y pagos.
"""
import base64
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError, AccessError


class TestLiquidacionV56(TransactionCase):
    def setUp(self):
        super().setUp()
        self.provider = self.env['res.partner'].create({'name':'Proveedor Transporte V56','is_company':True})
        partner_user = self.env['res.partner'].create({'name':'Acceso proveedor V56','parent_id':self.provider.id})
        self.supplier = self.env['res.users'].with_context(no_reset_password=True).create({
            'name':'Portal Proveedor V56', 'login':'proveedor.v56@example.invalid','partner_id':partner_user.id,
            'groups_id':[(6,0,[self.env.ref('base.group_portal').id,
                self.env.ref('logistica_transcash.group_transcash_transportista').id])],
        })
        self.manager = self.env['res.users'].with_context(no_reset_password=True).create({
            'name':'Jefe Logística V56','login':'jefe.logistica.v56@example.invalid',
            'groups_id':[(6,0,[self.env.ref('logistica_transcash.group_logistica_manager').id])],
        })
        self.accountant = self.env['res.users'].with_context(no_reset_password=True).create({
            'name':'Contabilidad V56','login':'contabilidad.v56@example.invalid',
            'groups_id':[(6,0,[self.env.ref('logistica_transcash.group_transcash_contabilidad').id])],
        })
        self.driver = self.env['res.users'].with_context(no_reset_password=True).create({
            'name':'Conductor V56','login':'conductor.v56@example.invalid',
            'groups_id':[(6,0,[self.env.ref('base.group_portal').id,
                self.env.ref('logistica_transcash.group_transcash_chofer').id])],
        })
        self.trips = self.env['transcash.embarque'].sudo()
        for n, price in [('0001',180),('0002',240)]:
            trip = self.env['transcash.embarque'].sudo().create({
                'name':'EMB/V56/'+n, 'company_id':self.env.company.id,
                'chofer_usuario_id':self.driver.id,'proveedor_id':self.provider.id,
                'placa':'ABC1234','state':'entregado', 'valor_acordado':price,
            })
            self.env['transcash.guia'].sudo().create({
                'name':'G/V56/'+n, 'company_id':self.env.company.id,
                'chofer_usuario_id':self.driver.id,'proveedor_id':self.provider.id,
                'embarque_id':trip.id, 'state':'entregada',
                'aprobacion_global':'aprobada', 'incidencia_estado':'ninguna',
            })
            self.trips |= trip

    def _approved(self):
        for trip in self.trips:
            trip.with_user(self.manager).action_approve_transport()

    def test_supplier_cannot_liquidate_without_manager_approval(self):
        with self.assertRaises(UserError):
            self.env['transcash.pago.liquidacion'].with_user(self.supplier).create_supplier_liquidation(self.trips.ids)

    def test_accountant_cannot_approve_rate(self):
        with self.assertRaises(AccessError):
            self.trips[0].with_user(self.accountant).action_approve_transport()

    def test_liquidation_and_partial_full_payment(self):
        self._approved()
        doc = self.env['transcash.pago.liquidacion'].with_user(self.supplier).create_supplier_liquidation(self.trips.ids)
        self.assertEqual(doc.total_acordado,420)
        with self.assertRaises(UserError):
            self.env['transcash.pago.liquidacion'].with_user(self.supplier).create_supplier_liquidation(self.trips.ids)
        pdf = base64.b64encode(b'%PDF-1.4\nmock').decode('ascii')
        doc.with_user(self.supplier).action_supplier_submit('FACT-V56','2026-10-15',420,63,pdf,'factura.pdf')
        self.assertEqual(doc.estado,'revision')
        doc.with_user(self.accountant).action_accounting_approve()
        self.assertEqual(doc.estado,'proceso_pago')
        doc.with_user(self.accountant).action_register_payment(200,'2026-10-15','TRANSF-001','transferencia',pdf,'abono.pdf')
        self.assertEqual(doc.estado,'parcial')
        self.assertAlmostEqual(doc.saldo_pendiente, 283)
        with self.assertRaises(UserError):
            doc.with_user(self.accountant).action_register_payment(300,'2026-10-15','TRANSF-EXCESO','transferencia',pdf,'exceso.pdf')
        doc.with_user(self.accountant).action_register_payment(283,'2026-10-15','TRANSF-002','transferencia',pdf,'saldo.pdf')
        self.assertEqual(doc.estado,'pagada')
        self.assertEqual(self.trips[0].estado_financiero,'pagada')

    def test_invoice_discrepancy_and_separation(self):
        self._approved()
        doc = self.env['transcash.pago.liquidacion'].with_user(self.supplier).create_supplier_liquidation(self.trips.ids)
        pdf = base64.b64encode(b'%PDF-1.4\nmock').decode('ascii')
        doc.with_user(self.supplier).action_supplier_submit('FACT-DIF','2026-10-15',410,63,pdf,'factura.pdf')
        with self.assertRaises(UserError):
            doc.with_user(self.accountant).action_accounting_approve()
        with self.assertRaises(AccessError):
            doc.with_user(self.supplier).action_accounting_approve()
        doc.with_user(self.accountant).action_accounting_observe('Subtotal diferente al flete aprobado')
        self.assertEqual(doc.estado,'observada')
        doc.with_user(self.supplier).action_supplier_submit('FACT-CORREGIDA','2026-10-15',420,63,pdf,'factura.pdf')
        self.assertEqual(doc.estado,'revision')
