"""Prueba aislada (no requiere servidor Odoo): códigos/alias, sin mezcla de destinos."""
import importlib.util
import types
import sys
from pathlib import Path
from types import SimpleNamespace as N

odoo = types.ModuleType('odoo')
odoo._ = lambda s: s
class HTTP:
    @staticmethod
    def route(*args, **kwargs):
        return lambda fn: fn
odoo.http = HTTP
odoo.exceptions = types.ModuleType('odoo.exceptions')
for name in ('UserError', 'AccessError', 'ValidationError'):
    setattr(odoo.exceptions, name, type(name, (Exception,), {}))
odoo.http.request = N()
expr = types.ModuleType('odoo.osv.expression')
expr.AND = lambda x: x
osv = types.ModuleType('odoo.osv')
osv.expression = expr
sys.modules.update({'odoo': odoo, 'odoo.exceptions': odoo.exceptions,
                    'odoo.http': odoo.http, 'odoo.osv': osv,
                    'odoo.osv.expression': expr})
for name in ('odoo.addons','odoo.addons.logistica_transcash',
             'odoo.addons.logistica_transcash.controllers'):
    sys.modules[name] = types.ModuleType(name)
mod = types.ModuleType('odoo.addons.logistica_transcash.controllers.operacion')
mod.TranscashOperaciones = type('TranscashOperaciones', (), {})
sys.modules[mod.__name__] = mod
p = Path(__file__).resolve().parents[1]/'controllers'/'route_pwa_strict.py'
spec = importlib.util.spec_from_file_location('target_v214', p)
target = importlib.util.module_from_spec(spec)
spec.loader.exec_module(target)
obj = target.TranscashOperacionFiltrada()
normalize = obj._normalized_destination_code
assert normalize('NAJ') == normalize(' - N A J  ')
assert normalize('\u200bNAJ\xa0') == 'NAJ'
assert normalize('NÁJ') == 'NAJ'
assert normalize('GYE') != 'NAJ'
company = N(id=1)
route_destination = N(id=7, company_id=company, codigo=' NAJ ', name='Narcisa de Jesús', ciudad='')
guide_destination = N(id=8, company_id=company, codigo='- NAJ\u00a0', name='NAJ', ciudad='')
route = N(company_id=company, destino_id=route_destination)
route._coincide_destino = lambda x: x.destino_id and x.destino_id.id == 7
guide = N(company_id=company, destino_id=guide_destination,
          destino_codigo=' -NAJ ', destino_ciudad='', destino='NAJ')
assert obj._destination_matches(route, guide, None)
# Códigos distintos y nombres visualmente similares NO habilitan viajes.
guide.destino_id = N(id=9, company_id=company, codigo='GYE', name='NAJ', ciudad='')
assert not obj._destination_matches(route, guide, None)
# Código ERP contradictorio con el maestro relacionado => bloquear.
guide.destino_id = guide_destination
guide.destino_codigo = 'GYE'
assert not obj._destination_matches(route, guide, None)
guide.destino_codigo = '-NAJ'
# Alias administrador: guía código NAJ, ruta con otro código histórico.
route_destination.codigo = 'NARCISA'
assert not obj._destination_matches(route, guide, None)
class FakeAliasCollection:
    def sudo(self): return self
    def search(self, domain):
        assert any(x[0]=='company_id' and x[2]==1 for x in domain)
        assert any(x[0]=='destino_id' and x[2]==7 for x in domain)
        return [N(codigo_normalizado='NAJ')]
class FakeEnv:
    def __getitem__(self, name):
        assert name == 'tc.destination.alias'
        return FakeAliasCollection()
target.request.env = FakeEnv()
target.request.httprequest = N()
assert obj._destination_matches(route, guide, None), 'Alias NAJ -> Narcisa habilita destino'
guide.destino_id.codigo = 'GYE'
assert not obj._destination_matches(route, guide, None), 'Alias no habilita GYE'
# Alias solo entre compañias del mismo ID.
other = N(id=2)
guide.company_id = other
assert not obj._destination_matches(route, guide, None)
print('PASS: normalización, equivalencia manual, contradicción, empresa, rechazo')
