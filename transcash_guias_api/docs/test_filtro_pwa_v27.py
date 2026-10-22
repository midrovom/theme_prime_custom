"""Pruebas locales de las reglas de identidad del selector PWA v2.7.

Sin Odoo instalado: carga solo las funciones de reglas, no controladores HTTP.
Ejecutar: python docs/test_filtro_pwa_v27.py
"""
import ast
import re
import unicodedata
from pathlib import Path
from types import SimpleNamespace

path = Path(__file__).resolve().parents[1] / 'controllers' / 'route_pwa_strict.py'
module = ast.parse(path.read_text())
selected = [node for node in module.body if isinstance(node, ast.FunctionDef) and
            node.name in ('_identity', '_legal_name', '_dest_name')]
klass = next(n for n in module.body if isinstance(n, ast.ClassDef) and n.name == 'TranscashOperacionFiltrada')
methods = [node for node in klass.body if isinstance(node, ast.FunctionDef) and
           node.name in ('_driver_matches', '_transport_matches', '_destination_matches', '_match')]
for method in methods:
    method.decorator_list = []
mock_class = ast.ClassDef(name='TestSelector', bases=[], keywords=[], body=methods, decorator_list=[])
code = ast.fix_missing_locations(ast.Module(body=selected + [mock_class], type_ignores=[]))
namespace = {'re': re, 'unicodedata': unicodedata}
exec(compile(code, str(path), 'exec'), namespace)

class Record(SimpleNamespace):
    def __bool__(self): return bool(self.__dict__.get('id'))
    def __eq__(self, other): return bool(other) and self.id == getattr(other, 'id', None)
    @property
    def commercial_partner_id(self): return self

class ListRecords(list):
    def filtered(self, callback): return ListRecords(v for v in self if callback(v))

class FakePartnerTable:
    def sudo(self): return self
    def with_context(self, **kwargs): return self
    def search(self, domain, limit=None): return ListRecords(partners)
    def search_count(self, domain): return len(partners)

class FakeEnv:
    def __getitem__(self, key):
        assert key == 'res.partner'
        return FakePartnerTable()

class FakeRequest:
    env = FakeEnv()

namespace['request'] = FakeRequest()
S = namespace['TestSelector']()

partner = Record(id=9, vat='1790013235001', name='EZTRANSLOGIST S.A.')
partners = [partner]
driver_partner = Record(id=101, vat='0913586442', name='CHAVEZ MORAN DIMAS')
user = Record(id=301, partner_id=driver_partner, login='0913586442')
destination = Record(id=12, codigo='NAJ', name='NARCISA DE JESUS', ciudad='NARCISA DE JESUS')
company = Record(id=3)
route = Record(company_id=company, destino_id=destination, chofer_usuario_id=user, proveedor_id=partner,
               _coincide_destino=lambda guide: bool(guide.destino_id == destination))
guide = Record(company_id=company, state='registrada', embarque_id=False, hoja_ruta_id=False,
               chofer_usuario_id=False, chofer_contacto_id=driver_partner, ruc_chofer='0913586442',
               proveedor_id=False, destino_id=False, destino_codigo='', destino_ciudad='', destino='BODEGA DE SALDOS')
source = Record(id=500, driver_id=Record(id=333, identification='0913586442'), driver_partner_id=driver_partner,
                transport_partner_id=False, transport_tax_raw='', transport_name='EZTRANSLOGIST S.A.',
                destination_id=False, destination_city='NARCISA DE JESUS', destination_address='BODEGA DE SALDOS')

assert S._match(route, guide, source) == (True, 'compatible'), 'Contactos ERP concordantes'
other_user = Record(id=302, partner_id=Record(id=102, vat='0911111111'), login='0911111111')
guide.chofer_usuario_id = other_user
assert S._match(route, guide, source) == (False, 'chofer'), 'Bloquear otro usuario asignado'
guide.chofer_usuario_id = False
source.driver_id.identification = '0922222222'
assert S._match(route, guide, source) == (False, 'chofer'), 'Bloquear documentos ERP contradictorios'
source.driver_id.identification = '0913586442'
source.transport_tax_raw = '0999999999001'
assert S._match(route, guide, source) == (False, 'transporte'), 'Bloquear otro RUC'
source.transport_tax_raw = ''
guide.destino_id = Record(id=99, codigo='OTRO', name='OTRO DESTINO')
assert S._match(route, guide, source) == (False, 'destino'), 'Bloquear otro destino'
guide.destino_id = False
guide.embarque_id = Record(id=1000)
assert S._match(route, guide, source) == (False, 'estado'), 'Bloquear embarque asignado'
guide.embarque_id = False
assert S._match(route, guide, None) == (False, 'destino'), 'No asumir equivalencia sin fuente'
source.transport_tax_raw = '1790013235001'
assert S._match(route, guide, source) == (True, 'compatible'), 'RUC válido de fuente'
source.transport_tax_raw = ''
guide.chofer_usuario_id = user
guide.proveedor_id = partner
guide.destino_id = destination
assert S._match(route, guide, None) == (True, 'compatible'), 'Relaciones completas'
source.driver_id.identification = '0922222222'
assert S._match(route, guide, source) == (False, 'chofer'), 'Rechazar choque ERP aunque usuario ya esté asignado'
source.driver_id.identification = '0913586442'
source.transport_tax_raw = '0999999999001'
assert S._match(route, guide, source) == (False, 'transporte'), 'Rechazar RUC ERP contradictorio aun si el vínculo existe'
print('OK: 11 escenarios de identidad, destino, estado y homologación ERP')
