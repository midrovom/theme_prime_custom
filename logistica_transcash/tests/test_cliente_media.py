"""Permisos de destinatario y galería V5.3. Ejecutar en una BD de pruebas con --test-enable."""
from odoo.tests.common import TransactionCase
from odoo.exceptions import AccessError, UserError


class TestClienteMedia(TransactionCase):
    def setUp(self):
        super().setUp()
        self.customer = self.env['res.partner'].create({
            'name': 'Cliente recepción V53', 'is_company': True,
        })
        self.customer_user = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Usuario cliente V53', 'login': 'cliente.v53@example.invalid',
            'partner_id': self.customer.id,
            'groups_id': [(6, 0, [self.env.ref('base.group_portal').id,
                         self.env.ref('logistica_transcash.group_transcash_cliente').id])],
        })
        self.guide = self.env['transcash.guia'].sudo().create({
            'name': 'GUIA-CLIENTE-V53', 'company_id': self.env.company.id,
            'destinatario_id': self.customer.id, 'state': 'destino',
        })
        self.other = self.env['transcash.guia'].sudo().create({
            'name': 'GUIA-AJENA-V53', 'company_id': self.env.company.id,
        })

    def test_customer_limited_to_their_guide(self):
        self.assertTrue(self.guide._is_recipient(self.customer_user))
        self.assertFalse(self.other._is_recipient(self.customer_user))
        with self.assertRaises(AccessError):
            self.guide.with_user(self.customer_user)._check_internal_gallery_access()

    def test_customer_receives_but_cannot_change_loading(self):
        service = self.env['transcash.evidencia'].with_user(self.customer_user)
        note = service.register_evidence(self.guide, 'cliente', 'Recepción con observaciones',
                                         False, False, False, 'otro')
        self.assertEqual(note.autor_usuario_id, self.customer_user)
        with self.assertRaises(UserError):
            service.register_evidence(self.guide, 'carga', 'Intento indebido de modificar carga',
                                      False, False, False)
