"""V5.26: entrada del cliente y aislamiento cuando hay perfiles Portal superpuestos."""
from types import SimpleNamespace
from unittest.mock import patch

from odoo.tests.common import TransactionCase
from ..controllers import landing, portal, embarque


class FakeEnv:
    def __init__(self, env, user):
        self._env, self.user = env, user
    def __getitem__(self, name):
        return self._env[name]


class TestPortalClienteV526(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        portal_group = cls.env.ref('base.group_portal')
        client_group = cls.env.ref('logistica_transcash.group_transcash_cliente')
        driver_group = cls.env.ref('logistica_transcash.group_transcash_chofer')
        cls.partner = cls.env['res.partner'].sudo().create({'name':'Cliente V526', 'is_company': True})
        cls.other_partner = cls.env['res.partner'].sudo().create({'name':'Destinatario ajeno V526'})
        cls.client = cls.env['res.users'].sudo().with_context(no_reset_password=True).create({
            'name':'Usuario cliente V526','login':'v526-cliente@example.invalid',
            'partner_id':cls.partner.id,
            'groups_id':[(6,0,[portal_group.id,client_group.id])],
        })
        cls.missing_group = cls.env['res.users'].sudo().with_context(no_reset_password=True).create({
            'name':'Portal sin perfil V526','login':'v526-sinperfil@example.invalid',
            'groups_id':[(6,0,[portal_group.id])],
        })
        cls.dual_role = cls.env['res.users'].sudo().with_context(no_reset_password=True).create({
            'name':'Portal doble perfil V526','login':'v526-duplicado@example.invalid',
            'partner_id':cls.partner.id,
            'groups_id':[(6,0,[portal_group.id,client_group.id,driver_group.id])],
        })
        cls.own = cls.env['transcash.guia'].sudo().create({
            'name':'GUIA-CLIENTE-526','destinatario_id':cls.partner.id,
        })
        cls.other = cls.env['transcash.guia'].sudo().create({
            'name':'GUIA-AJENA-526','destinatario_id':cls.other_partner.id,
        })

    def fake_request(self, user):
        return SimpleNamespace(
            env=FakeEnv(self.env, user),
            redirect=lambda path: ('redirect', path),
            render=lambda template, values: ('render', template, values),
            not_found=lambda: ('not_found',),
        )

    def test_portal_requires_transcash_customer_group(self):
        self.assertTrue(self.client.share)
        self.assertTrue(self.client.has_group('logistica_transcash.group_transcash_cliente'))
        self.assertFalse(landing.TranscashLanding._home_for_user(self.missing_group))
        self.assertEqual(landing.TranscashLanding._home_for_user(self.client), '/transcash/guias')
        self.assertEqual(landing.TranscashLanding._home_for_user(self.dual_role), '/transcash/guias')

    def test_missing_group_gets_configuration_message(self):
        with patch.object(landing,'request', self.fake_request(self.missing_group)):
            res = landing.TranscashLanding().landing()
        self.assertEqual(res[0], 'render')
        self.assertEqual(res[1], 'logistica_transcash.portal_falta_perfil')

    def test_customer_alias_only_redirects_to_authorized_customer_url(self):
        with patch.object(landing,'request', self.fake_request(self.client)):
            self.assertEqual(landing.TranscashLanding().client_entry(), ('redirect','/transcash/guias'))
        with patch.object(landing,'request', self.fake_request(self.missing_group)):
            self.assertEqual(landing.TranscashLanding().client_entry(), ('redirect','/transcash'))

    def test_old_trip_link_returns_to_customer_receptions(self):
        with patch.object(embarque,'request',self.fake_request(self.client)):
            self.assertEqual(embarque.EmbarquePortal().embark_detail(999),
                             ('redirect','/transcash/guias'))
        with patch.object(portal,'request',self.fake_request(self.missing_group)):
            res = portal.TranscashPortal().guides()
        self.assertEqual(res[:2], ('render','logistica_transcash.portal_falta_perfil'))

    def test_customer_can_only_see_own_guides(self):
        with patch.object(portal,'request',self.fake_request(self.client)):
            domain = portal.TranscashPortal()._visible_domain()
            guides = self.env['transcash.guia'].sudo().search(domain)
            self.assertIn(self.own, guides)
            self.assertNotIn(self.other, guides)
            self.assertEqual(portal.TranscashPortal()._guide(self.own.id), self.own)
            self.assertFalse(portal.TranscashPortal()._guide(self.other.id))

    def test_client_cannot_open_trip_even_with_driver_group(self):
        with patch.object(embarque,'request',self.fake_request(self.dual_role)):
            result = embarque.EmbarquePortal().list_embarks()
        self.assertEqual(result, ('redirect', '/transcash/guias'))
        with patch.object(portal,'request',self.fake_request(self.dual_role)):
            self.assertFalse(portal.TranscashPortal()._guide(self.other.id))
