"""Pruebas de la comparación estricta por código ERP sin servidor Odoo."""
from pathlib import Path
from types import SimpleNamespace as NS
import ast
import re
import unicodedata

root = Path(__file__).resolve().parents[1]
script = root / 'controllers' / 'route_pwa_strict.py'
parsed = ast.parse(script.read_text())
klass = next(c for c in parsed.body if isinstance(c, ast.ClassDef) and c.name == 'TranscashOperacionFiltrada')
methods = {'_normalized_destination_code', '_erp_destination_code', '_destination_matches'}
subset = ast.Module(body=[ast.ClassDef(name='Filter', bases=[], keywords=[], body=[m for m in klass.body if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)) and m.name in methods], decorator_list=[])], type_ignores=[])
ast.fix_missing_locations(subset)
namespace = {'re': re, 'unicodedata': unicodedata}
exec(compile(subset, str(script), 'exec'), namespace)
Filter = namespace['Filter']
obj = Filter()
company = NS(id=1)
master = NS(codigo='NAJ')
ruta = NS(company_id=company, destino_id=master)
guia = NS(company_id=company, destino_codigo=' - N A J ', destino_id=NS(id=777, codigo='OTRO'))
assert obj._destination_matches(ruta, guia, None), 'Códigos normalizados iguales aunque los M2O sean diferentes'
source = NS(destination_id=NS(external_code='- NAJ  '))
assert obj._destination_matches(ruta, guia, source), 'Debe utilizar el código ERP recibido'
source = NS(destination_id=NS(external_code='OTRO'))
assert not obj._destination_matches(ruta, guia, source), 'No utilizar el código de la guía si el del ERP difiere'
source = NS(destination_id=False)
assert not obj._destination_matches(ruta, guia, source), 'No aceptar coincidencias si la API no envió código'
source = NS(destination_id=NS(external_code='  \u00a0\u200b -NAJ . '))
assert obj._destination_matches(ruta, guia, source), 'Debe ignorar espacios invisibles y separadores'
source = NS(destination_id=NS(external_code='NAJ2'))
assert not obj._destination_matches(ruta, guia, source), 'No aceptar códigos distintos'
assert not obj._destination_matches(NS(company_id=NS(id=2), destino_id=master), guia, None), 'Multiempresa'
assert not obj._destination_matches(ruta, NS(company_id=company, destino_codigo='', destino_id=master), None), 'Sin código ERP ni staging no hay coincidencia'

publication = (root/'models'/'publication.py').read_text()
assert "self.destination_id.external_code if self.destination_id else False" in publication
assert 'views/destination_alias_views.xml' not in (root/'__manifest__.py').read_text()
assert 'tc.destination.alias' not in script.read_text()
print('OK 10 pruebas: código ERP directo, normalización, ausencia, empresa, sin alias y persistencia')
