"""Pruebas unitarias sin servidor: python docs/test_destinos_v228.py"""
import importlib.util
import pathlib
import sys
import types
import unittest

# Stub de imports Odoo: solo se prueban helpers puros y altas del catálogo.
odoo = types.ModuleType('odoo')
api = types.SimpleNamespace(model=lambda f: f)
odoo.api = api
odoo.models = types.SimpleNamespace(Model=type('Model', (), {}))
odoo._ = lambda value: value
exceptions = types.ModuleType('odoo.exceptions')
exceptions.AccessError = type('AccessError', (Exception,), {})
exceptions.ValidationError = type('ValidationError', (Exception,), {})
sys.modules['odoo'] = odoo
sys.modules['odoo.exceptions'] = exceptions
path = pathlib.Path(__file__).resolve().parents[1] / 'models' / 'destination_codes.py'
spec = importlib.util.spec_from_file_location('destination_erp_test', path)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class Destination:
    def __init__(self, **vals):
        self.__dict__.update(vals)
    def write(self, vals):
        self.__dict__.update(vals)


class DestinationsModel:
    def __init__(self):
        self.rows = {}
    def sudo(self):
        return self
    def with_context(self, **_):
        return self
    def browse(self, ident):
        return self.rows[ident]
    def create(self, vals):
        next_id = max(self.rows, default=0) + 1
        rec = Destination(id=next_id, active=True, **vals)
        self.rows[next_id] = rec
        return rec


class FakeCursor:
    def __init__(self, model):
        self.model = model
        self.results = []
    def execute(self, query, params):
        if 'FROM transcash_destino' in query:
            company_id, key = params
            self.results = [(rec.id,) for rec in self.model.rows.values()
                            if rec.company_id == company_id
                            and mod.erp_destination_key(rec.codigo) == key]
        else:
            self.results = []
    def fetchall(self):
        return self.results


class FakeEnv:
    def __init__(self):
        self.model = DestinationsModel()
        self.cr = FakeCursor(self.model)
    def __getitem__(self, model):
        assert model == 'transcash.destino', model
        return self.model


class DestinoERPTests(unittest.TestCase):
    def test_normalizaciones(self):
        for code in ('NAJ', ' NAJ ', '-NAJ', 'N A J', 'naj', '\u00a0NAJ\u00a0'):
            self.assertEqual(mod.erp_destination_key(code), 'NAJ')
        self.assertEqual(mod.erp_destination_code(' -naj  '), 'NAJ')
        self.assertEqual(mod.erp_destination_code('GYE-001'), 'GYE-001')
        self.assertEqual(mod.erp_destination_code(' N A J '), 'NAJ')

    def test_creacion_repetida_sin_duplicado(self):
        env = FakeEnv()
        first = mod.upsert_erp_destination(env, 1, ' NAJ ', 'Narcisa de Jesus')
        second = mod.upsert_erp_destination(env, 1, '-naj', 'NARCISA DE JESUS')
        self.assertEqual(first.id, second.id)
        self.assertEqual(len(env.model.rows), 1)
        self.assertEqual(second.codigo, 'NAJ')
        self.assertEqual(second.name, 'NARCISA DE JESUS')
        self.assertEqual(second.ciudad, 'NARCISA DE JESUS')

    def test_companias_independientes(self):
        env = FakeEnv()
        mod.upsert_erp_destination(env, 1, 'NAJ', 'Narcisa')
        mod.upsert_erp_destination(env, 2, 'NAJ', 'Narcisa')
        self.assertEqual(len(env.model.rows), 2)

    def test_archivado_no_se_duplica_ni_reactiva(self):
        env = FakeEnv()
        existing = mod.upsert_erp_destination(env, 1, 'NAJ', 'Narcisa')
        existing.active = False
        again = mod.upsert_erp_destination(env, 1, '-NAJ', 'Narcisa nueva')
        self.assertEqual(again.id, existing.id)
        self.assertFalse(again.active)
        self.assertEqual(len(env.model.rows), 1)

    def test_duplicados_historicos_no_crean_tercero(self):
        env = FakeEnv()
        env.model.create({'company_id': 1, 'codigo': 'NAJ', 'name': 'Narcisa', 'ciudad': 'Narcisa', 'fuente': 'erp'})
        env.model.create({'company_id': 1, 'codigo': 'NA-J', 'name': 'Narcisa', 'ciudad': 'Narcisa', 'fuente': 'manual'})
        with self.assertRaises(exceptions.ValidationError):
            mod.upsert_erp_destination(env, 1, 'NAJ', 'Narcisa')
        self.assertEqual(len(env.model.rows), 2)

    def test_sin_codigo_no_crea(self):
        env = FakeEnv()
        self.assertFalse(mod.upsert_erp_destination(env, 1, '', 'Narcisa'))
        self.assertEqual(len(env.model.rows), 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
