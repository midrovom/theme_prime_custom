"""V5.28: perfiles Portal gestionados desde Logística y Contabilidad.

Ejecutar en Odoo 18: -i/ -u logistica_transcash --test-enable --stop-after-init
No se ejecutan con Python puro (requieren ORM y PostgreSQL).
"""
from odoo.tests.common import TransactionCase
from odoo.exceptions import AccessError, UserError, ValidationError


class TestAccesosPortalV528(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.portal_group = cls.env.ref('base.group_portal')
        cls.manager_group = cls.env.ref('logistica_transcash.group_logistica_manager')
        cls.account_group = cls.env.ref('logistica_transcash.group_transcash_contabilidad')
        cls.client_group = cls.env.ref('logistica_transcash.group_transcash_cliente')
        cls.supplier_group = cls.env.ref('logistica_transcash.group_transcash_transportista')
        cls.driver_group = cls.env.ref('logistica_transcash.group_transcash_chofer')

        cls.client_contact = cls.env['res.partner'].create({'name': 'Cliente prueba acceso V528', 'is_company': True})
        cls.supplier_company = cls.env['res.partner'].create({'name': 'Transporte prueba V528', 'is_company': True})
        cls.supplier_contact = cls.env['res.partner'].create({
            'name': 'Representante V528', 'parent_id': cls.supplier_company.id,
            'email': 'proveedor.v528@example.com'})

        cls.client_user = cls._new_user('cliente.v528', cls.client_contact, [cls.portal_group])
        cls.supplier_user = cls._new_user('proveedor.v528', cls.supplier_contact, [cls.portal_group])
        cls.manager = cls._new_user('logistica.v528', None, [cls.env.ref('base.group_user'), cls.manager_group])
        cls.accountant = cls._new_user('contabilidad.v528', None, [cls.env.ref('base.group_user'), cls.account_group])

    @classmethod
    def _new_user(cls, login, partner, groups):
        vals = {'name': login, 'login': login, 'groups_id': [(6, 0, [g.id for g in groups])],
                'company_id': cls.company.id, 'company_ids': [(6, 0, [cls.company.id])]}
        if partner:
            vals['partner_id'] = partner.id
        return cls.env['res.users'].sudo().with_context(no_reset_password=True).create(vals)

    def test_client_enabled_only_by_logistics_and_receives_no_backend(self):
        access = self.env['transcash.acceso.cliente'].with_user(self.manager).create({
            'usuario_id': self.client_user.id, 'company_id': self.company.id})
        self.assertFalse(access.acceso_habilitado)
        access.action_activar_acceso()
        self.assertTrue(self.client_user.has_group('logistica_transcash.group_transcash_cliente'))
        self.assertFalse(self.client_user.has_group('base.group_user'))
        self.assertFalse(self.client_user.has_group('logistica_transcash.group_transcash_transportista'))
        self.assertEqual(access.action_ver_guias()['res_model'], 'transcash.guia')
        with self.assertRaises(AccessError):
            access.with_user(self.accountant).action_desactivar_acceso()
        access.action_desactivar_acceso()
        self.assertFalse(self.client_user.has_group('logistica_transcash.group_transcash_cliente'))

    def test_supplier_enabled_by_accounting_and_is_company_scoped(self):
        access = self.env['transcash.acceso.proveedor'].with_user(self.accountant).create({
            'usuario_id': self.supplier_user.id, 'company_id': self.company.id})
        access.action_activar_acceso()
        self.assertTrue(self.supplier_user.has_group('logistica_transcash.group_transcash_transportista'))
        self.assertFalse(self.supplier_user.has_group('base.group_user'))
        self.assertEqual(self.env['transcash.acceso.proveedor']._allowed_companies_for(self.supplier_user), [self.company.id])
        self.assertEqual(access.action_ver_viajes()['res_model'], 'transcash.embarque')
        self.assertEqual(access.action_ver_liquidaciones()['res_model'], 'transcash.pago.liquidacion')
        with self.assertRaises(AccessError):
            access.with_user(self.manager).action_desactivar_acceso()
        access.action_desactivar_acceso()
        self.assertEqual(self.env['transcash.acceso.proveedor']._allowed_companies_for(self.supplier_user), [])
        self.assertFalse(self.supplier_user.has_group('logistica_transcash.group_transcash_transportista'))

    def test_accountant_cannot_create_client_and_manager_cannot_create_supplier(self):
        with self.assertRaises(AccessError):
            self.env['transcash.acceso.cliente'].with_user(self.accountant).create({
                'usuario_id': self.client_user.id, 'company_id': self.company.id})
        with self.assertRaises(AccessError):
            self.env['transcash.acceso.proveedor'].with_user(self.manager).create({
                'usuario_id': self.supplier_user.id, 'company_id': self.company.id})

    def test_cannot_grant_supplier_to_driver_or_client_account(self):
        self.client_user.sudo().write({'groups_id': [(4, self.client_group.id)]})
        access = self.env['transcash.acceso.proveedor'].with_user(self.accountant).create({
            'usuario_id': self.client_user.id, 'company_id': self.company.id})
        with self.assertRaises(UserError):
            access.action_activar_acceso()
        self.client_user.sudo().write({'groups_id': [(3, self.client_group.id), (4, self.driver_group.id)]})
        with self.assertRaises(UserError):
            access.action_activar_acceso()

    def test_internal_user_is_not_portal(self):
        with self.assertRaises(ValidationError):
            self.env['transcash.acceso.cliente'].with_user(self.manager).create({
                'usuario_id': self.manager.id, 'company_id': self.company.id})

    def test_partner_cannot_be_swapped_after_creation(self):
        access = self.env['transcash.acceso.cliente'].with_user(self.manager).create({
            'usuario_id': self.client_user.id, 'company_id': self.company.id})
        with self.assertRaises(AccessError):
            access.write({'usuario_id': self.supplier_user.id})
        with self.assertRaises(AccessError):
            access.write({'activo': False})

    def test_legacy_supplier_without_register_keeps_legacy_scope(self):
        self.assertIsNone(self.env['transcash.acceso.proveedor']._allowed_companies_for(self.supplier_user))
