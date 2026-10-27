# -*- coding: utf-8 -*-
"""Pruebas de transporte GET alternativo sin contactar al ERP."""
from types import SimpleNamespace
from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestBudgetERPTransport(TransactionCase):
    def _api_stub(self, **changes):
        values = {
            'id': 45,
            'url': 'https://erp.invalid/erp-base/',
            'end_point': '/inventory_odoo/consulta_odoo/getctagastos/2',
            'user_id': 'example',
            'password': 'secret',
            'ensure_one': lambda: None,
        }
        values.update(changes)
        return SimpleNamespace(**values)

    def test_fallback_get_uses_existing_credentials_and_base_url(self):
        response = SimpleNamespace(
            status_code=200,
            raise_for_status=lambda: None,
            json=lambda: {'data': [{'Codigo': '601', 'Nombre': 'Prueba'}]},
        )
        with patch('odoo.addons.expense_budget_control.models.api_transport.requests.get',
                   return_value=response) as get:
            data = self.env['expense.budget.api.transport']._http_get_json(
                self._api_stub())
        self.assertEqual(data['data'][0]['Codigo'], '601')
        args, kwargs = get.call_args
        self.assertEqual(args[0],
                         'https://erp.invalid/erp-base/inventory_odoo/consulta_odoo/getctagastos/2')
        self.assertEqual(kwargs['headers']['userid'], 'example')
        self.assertEqual(kwargs['headers']['password'], 'secret')
        self.assertEqual(kwargs['headers']['framework'], 'PRUEBAS')
        self.assertTrue(kwargs['timeout'][1] >= 60)

    def test_absolute_endpoint_url(self):
        record = self._api_stub(end_point='https://erp2.invalid/any/path')
        response = SimpleNamespace(status_code=200, raise_for_status=lambda: None,
                                   json=lambda: {'data': []})
        with patch('odoo.addons.expense_budget_control.models.api_transport.requests.get',
                   return_value=response) as get:
            self.env['expense.budget.api.transport']._http_get_json(record)
        self.assertEqual(get.call_args.args[0], 'https://erp2.invalid/any/path')

    def test_missing_credentials_blocks_http(self):
        with patch('odoo.addons.expense_budget_control.models.api_transport.requests.get') as get:
            with self.assertRaises(UserError):
                self.env['expense.budget.api.transport']._http_get_json(
                    self._api_stub(password=''))
            get.assert_not_called()

    def test_bad_http_status(self):
        import requests
        def raise_401():
            raise requests.exceptions.HTTPError('Unauthorized')
        response = SimpleNamespace(status_code=401, raise_for_status=raise_401)
        with patch('odoo.addons.expense_budget_control.models.api_transport.requests.get',
                   return_value=response):
            with self.assertRaisesRegex(UserError, '401'):
                self.env['expense.budget.api.transport']._http_get_json(self._api_stub())
