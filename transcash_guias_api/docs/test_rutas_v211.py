"""Self-contained regression for critical identity comparisons (without Odoo server)."""
import importlib.util
import sys
import types
from pathlib import Path
from types import SimpleNamespace as N

odoo = types.ModuleType('odoo')
odoo._ = lambda v: v
class HTTP:
    @staticmethod
    def route(*args, **kwargs):
        return lambda fn: fn
odoo.http = HTTP
odoo.exceptions = types.ModuleType('odoo.exceptions')
for name in ('UserError','AccessError','ValidationError'):
    setattr(odoo.exceptions, name, type(name, (Exception,), {}))
odoo.http.request = N()
expr = types.ModuleType('odoo.osv.expression')
expr.AND = lambda expressions: expressions
osv = types.ModuleType('odoo.osv')
osv.expression = expr
sys.modules.update({'odoo':odoo,'odoo.exceptions':odoo.exceptions,
                    'odoo.http':odoo.http,'odoo.osv':osv,'odoo.osv.expression':expr})
for name in ('odoo.addons','odoo.addons.logistica_transcash',
             'odoo.addons.logistica_transcash.controllers'):
    sys.modules[name] = types.ModuleType(name)
mod = types.ModuleType('odoo.addons.logistica_transcash.controllers.operacion')
mod.TranscashOperaciones = type('TranscashOperaciones',(),{})
sys.modules[mod.__name__]=mod
p = Path(__file__).resolve().parents[1]/'controllers'/'route_pwa_strict.py'
spec = importlib.util.spec_from_file_location('test_route_v211_target', p)
target = importlib.util.module_from_spec(spec)
spec.loader.exec_module(target)
obj = target.TranscashOperacionFiltrada()
co = N(id=1, name='My Company')
raw = N(id=8, company_id=co, codigo='-NAJ', name='NAJ', ciudad='')
can = N(id=14, company_id=co, codigo='NAJ', name='Narcisa de Jesus', ciudad='')
other = N(id=15, company_id=co, codigo='GYE', name='Guayaquil', ciudad='')
partner_guide = N(id=29, vat='0914936729', name='WILSON', commercial_partner_id=None)
partner_route = N(id=30, vat='0914936729', name='WILSON', commercial_partner_id=None)
partner_guide.commercial_partner_id = partner_guide
partner_route.commercial_partner_id = partner_route
user_guide = N(id=11, partner_id=partner_guide, login='TRANSPCHAVEZ', name='WILSON')
user_route = N(id=12, partner_id=partner_route, login='0914936729', name='WILSON')
provider_a = N(id=101,vat='0992415290001',name='LOGITRACSA',commercial_partner_id=None)
provider_b = N(id=102,vat='0992415290001',name='LOGITRACSA',commercial_partner_id=None)
provider_bad = N(id=103,vat='1790013235001',name='OTRO',commercial_partner_id=None)
for p in (provider_a,provider_b,provider_bad):
    p.commercial_partner_id=p
ruta = N(company_id=co,destino_id=can,chofer_usuario_id=user_route,proveedor_id=provider_b)
ruta._coincide_destino=lambda guide: guide.destino_id==can
guia = N(company_id=co,state='registrada',embarque_id=False,hoja_ruta_id=False,
         destino_id=raw,destino='',destino_codigo='-NAJ',destino_ciudad='',
         chofer_usuario_id=user_guide,ruc_chofer='0914936729',chofer_contacto_id=partner_guide,
         proveedor_id=provider_a,name='32802',numero_documento='TR-53968',external_id_erp='001-005-000032802')
assert obj._destination_matches(ruta,guia,None), 'Equivalent NAJ destination must match'
assert obj._driver_matches(ruta,guia,None), 'Driver with verified same ID must match'
assert obj._transport_matches(ruta,guia,None), 'Supplier with same VAT must match'
assert obj._match(ruta,guia,None) == (True,'compatible')
assert obj._guide_diagnostic(ruta,guia,None)['compatible']
guia.destino_id=other
assert not obj._destination_matches(ruta,guia,None), 'Distinct destination must fail'
guia.destino_id=raw
guia.ruc_chofer='0910000000'
assert not obj._driver_matches(ruta,guia,None), 'Conflicting driver ID must fail'
guia.ruc_chofer='0914936729'
guia.proveedor_id=provider_bad
assert not obj._transport_matches(ruta,guia,None), 'Different company VAT must fail'
guia.proveedor_id=provider_a
guia.embarque_id=N(id=88)
assert obj._match(ruta,guia,None) == (False,'estado'), 'Already shipped guides fail'
print('PASS 9 identity, security and state assertions')
