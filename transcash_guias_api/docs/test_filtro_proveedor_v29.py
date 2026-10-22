"""Regresión independiente del filtro de proveedor de transporte (sin entorno Odoo).
Ejecutar: python docs/test_filtro_proveedor_v29.py
"""
import ast
import re
import unicodedata
from pathlib import Path
from types import SimpleNamespace

path = Path(__file__).resolve().parents[1] / 'controllers' / 'route_pwa_strict.py'
tree = ast.parse(path.read_text())
helpers = [x for x in tree.body if isinstance(x, ast.FunctionDef) and
           x.name in ('_identity', '_fiscal_id', '_legal_name', '_dest_name')]
klass = next(x for x in tree.body if isinstance(x, ast.ClassDef) and x.name == 'TranscashOperacionFiltrada')
methods = [x for x in klass.body if isinstance(x, ast.FunctionDef) and
           x.name in ('_transport_matches', '_driver_matches', '_destination_matches', '_match')]
for m in methods:
    m.decorator_list = []
mini = ast.ClassDef(name='Selector', bases=[], keywords=[], body=methods, decorator_list=[])
ns = {'re': re, 'unicodedata': unicodedata}
exec(compile(ast.fix_missing_locations(ast.Module(body=helpers + [mini], type_ignores=[])), str(path), 'exec'), ns)

class Rec(SimpleNamespace):
    def __bool__(self): return bool(getattr(self, 'id', None))
    @property
    def commercial_partner_id(self): return getattr(self, 'parent_company', None) or self

class Records(list):
    def filtered(self, fn): return Records(x for x in self if fn(x))

class PartnerTable:
    def sudo(self): return self
    def with_context(self, **kw): return self
    def search_count(self, domain): return len(partners)
    def search(self, domain, limit=None): return Records(partners[:limit])

class Env:
    def __getitem__(self, key):
        assert key == 'res.partner'
        return PartnerTable()

ns['request'] = SimpleNamespace(env=Env())
s = ns['Selector']()
transport = Rec(id=8, vat='0992415290001', name='EZTRANSLOGIST S.A.')
other_transport = Rec(id=9, vat='1790013235001', name='OTRO TRANSPORTE S.A.')
driver_contact = Rec(id=70, vat='0913586442', name='CHOFER A')
user = Rec(id=100, partner_id=driver_contact, login='0913586442')
company = Rec(id=2)
dest = Rec(id=14, codigo='NAJ', name='NARCISA DE JESUS', ciudad='')
route = Rec(proveedor_id=transport, company_id=company, chofer_usuario_id=user,
            destino_id=dest, _coincide_destino=lambda g: bool(g.destino_id and g.destino_id.id == dest.id))
guide = Rec(id=123, proveedor_id=transport, company_id=company, chofer_usuario_id=user,
            chofer_contacto_id=driver_contact, ruc_chofer='0913586442',
            destino_id=dest, state='registrada', embarque_id=False, hoja_ruta_id=False)
source = Rec(id=7, transport_tax_raw='1790013235001', transport_partner_id=other_transport,
             transport_name='OTRO TRANSPORTE S.A.', driver_id=False, driver_partner_id=False,
             destination_id=False)
partners = [transport, other_transport]

# Registro del proveedor en la guía tiene precedencia sobre vínculos ERP desactualizados.
assert s._transport_matches(route, guide, source) is True
assert s._match(route, guide, source) == (True, 'compatible')
# Un contacto secundario de la empresa transportista también debe ser válido.
child = Rec(id=56, vat='', name='Contacto de operaciones', parent_company=transport)
guide.proveedor_id = child
assert s._transport_matches(route, guide, source) is True
# Duplicados históricos de res.partner: mismo RUC, distintos IDs.
guide.proveedor_id = Rec(id=33, vat='099-2415290-001', name='EZTRANSLOGIST S.A.')
assert s._transport_matches(route, guide, source) is True
# Otro RUC en proveedor operativo no se debe admitir, aun con fuente coincidente.
guide.proveedor_id = other_transport
source.transport_partner_id = transport
source.transport_tax_raw = transport.vat
assert s._transport_matches(route, guide, source) is False
# Con proveedor operativo vacío, se puede recuperar por fuente con VAT compatible.
guide.proveedor_id = False
assert s._transport_matches(route, guide, source) is True
# Sin ninguna referencia confirmada al proveedor, no admitir.
source.transport_partner_id = False
source.transport_tax_raw = ''
source.transport_name = 'OTRA EMPRESA'
assert s._transport_matches(route, guide, source) is False
# RUC ilegible/no fiscal nunca se usa como coincidencia numérica.
source.transport_tax_raw = 'PRE0078'
assert s._transport_matches(route, guide, source) is False
print('OK: 7 verificaciones de proveedor_id, RUC y fallback ERP')
