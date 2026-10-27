"""Pruebas autocontenidas del selector de identidad fiscal del importador.

Ejecutar: python tests/test_fiscal_v224.py
No necesitan base Odoo; la actualización real sí requiere instalación en Odoo.
"""
import contextlib
import importlib.util
import pathlib
import sys
import types
import unittest

odoo = types.ModuleType('odoo')
odoo._ = lambda value: value
exc = types.ModuleType('odoo.exceptions')
class ValidationError(Exception):
    pass
class UserError(Exception):
    pass
exc.ValidationError = ValidationError
exc.UserError = UserError
sys.modules['odoo'] = odoo
sys.modules['odoo.exceptions'] = exc
file = pathlib.Path(__file__).resolve().parents[1] / 'models' / 'fiscal_identity.py'
spec = importlib.util.spec_from_file_location('fiscal_identity_v224', file)
fiscal = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fiscal)

class IDType:
    _fields = {'country_id', 'code'}
    def __init__(self, id, name, code, country_id):
        self.id, self.name, self.code, self.country_id = id, name, code, country_id
    def __getitem__(self, key):
        return getattr(self, key)

class IDTypes:
    def __init__(self, items):
        self.items = items
    def sudo(self):
        return self
    def search(self, domain):
        return self.items

class Partners:
    _fields = {'l10n_latam_identification_type_id'}
    def __init__(self, idtypes):
        self.records = []
        self.idtypes = idtypes
    def sudo(self):
        return self
    def with_context(self, **kwargs):
        return self
    def create(self, vals):
        # Simula Odoo en compañía ecuatoriana: RUC 13 inválido se rechaza.
        ruc = vals['l10n_latam_identification_type_id'] == 1
        cedula = vals['l10n_latam_identification_type_id'] == 2
        if ruc and vals['vat'] == '1234567890123':
            raise ValidationError('RUC inválido')
        if cedula and vals['vat'] == '0000000000':
            raise ValidationError('Cédula inválida')
        result = types.SimpleNamespace(id=len(self.records) + 1, **vals)
        self.records.append(result)
        return result

class FakeEnv:
    def __init__(self):
        ec = types.SimpleNamespace(id=61)
        self.types = IDTypes([
            IDType(1, 'RUC', 'ruc', ec),
            IDType(2, 'Cédula', 'cedula', ec),
            IDType(3, 'Identificación extranjera', 'foreign', ec),
        ])
        self.partners = Partners(self.types)
        self.registry = types.SimpleNamespace(models={'l10n_latam.identification.type': True})
        self.cr = types.SimpleNamespace(savepoint=lambda: contextlib.nullcontext())
    def __getitem__(self, model):
        return {'res.partner': self.partners, 'l10n_latam.identification.type': self.types}[model]
    def ref(self, xmlid, raise_if_not_found=False):
        return types.SimpleNamespace(id=61) if xmlid == 'base.ec' else False

class FiscalTests(unittest.TestCase):
    def test_identification_normalization(self):
        self.assertEqual(fiscal.fiscal_document(' EC-099 2415290 001 '), '0992415290001')
        self.assertEqual(fiscal.fiscal_variants('0992415290001'),
                         {'0992415290001', 'EC0992415290001'})
        self.assertEqual(fiscal.fiscal_document('AB-123.45'), 'AB12345')
    def test_valid_ruc(self):
        env = FakeEnv()
        item, kind, warning = fiscal.create_fiscal_partner(env, {'name': 'Transportista'},
                                                          '0992415290001', 'transport')
        self.assertEqual(kind, 'ruc')
        self.assertEqual(item.l10n_latam_identification_type_id, 1)
        self.assertEqual(len(env.partners.records), 1)
    def test_invalid_ruc_falls_back_foreign_without_duplicate(self):
        env = FakeEnv()
        item, kind, warning = fiscal.create_fiscal_partner(env, {'name': 'Transportista'},
                                                          '1234567890123', 'transport')
        self.assertEqual(kind, 'foreign')
        self.assertEqual(item.vat, '1234567890123')
        self.assertIn('rechazado', warning)
        self.assertEqual(len(env.partners.records), 1)
    def test_foreign_supplier_11_digits(self):
        env = FakeEnv()
        item, kind, warning = fiscal.create_fiscal_partner(env, {'name': 'Transportista'},
                                                          '20101026001', 'transport')
        self.assertEqual(kind, 'foreign')
        self.assertEqual(item.l10n_latam_identification_type_id, 3)
    def test_driver_cedula(self):
        env = FakeEnv()
        item, kind, warning = fiscal.create_fiscal_partner(env, {'name': 'Chofer'},
                                                          '0913586442', 'driver')
        self.assertEqual(kind, 'cedula')
    def test_driver_bad_cedula_fallback(self):
        env = FakeEnv()
        item, kind, warning = fiscal.create_fiscal_partner(env, {'name': 'Chofer'},
                                                          '0000000000', 'driver')
        self.assertEqual(kind, 'foreign')
    def test_foreign_type_missing_refuses(self):
        env = FakeEnv()
        env.types.items = [x for x in env.types.items if x.code != 'foreign']
        with self.assertRaises(ValidationError):
            fiscal.create_fiscal_partner(env, {'name': 'Proveedor'}, '20101026001', 'transport')
        self.assertFalse(env.partners.records)

if __name__ == '__main__':
    unittest.main(verbosity=2)
