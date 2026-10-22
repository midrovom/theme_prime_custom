"""Test focalizado del destino operativo. Ejecutar: python docs/test_destinos_v216.py."""
import ast
import re
import unicodedata
from pathlib import Path
from types import SimpleNamespace as NS

src = Path(__file__).resolve().parents[1] / 'controllers' / 'route_pwa_strict.py'
tree = ast.parse(src.read_text())
cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'TranscashOperacionFiltrada')
chosen = {'_normalized_destination_code', '_guide_destination_value', '_destination_matches'}
cls.body = [n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name in chosen]
cls.name = 'SelectorPrueba'
cls.bases = []
cls.keywords = []
mini = ast.Module(body=[cls], type_ignores=[])
ast.fix_missing_locations(mini)
space = {'re': re, 'unicodedata': unicodedata}
exec(compile(mini, str(src), 'exec'), space)
selector = space['SelectorPrueba']()
co = NS(id=1)
route = NS(company_id=co, destino_id=NS(codigo='NAJ', id=123))
for code in ('NAJ', ' NAJ ', ' -NAJ ', '\u200bNAJ\xa0', 'N A J'):
    guide = NS(company_id=co, destino=code, destino_codigo='OTRO', destino_id=NS(codigo='OTRO'))
    assert selector._destination_matches(route, guide, NS(destination_id=NS(external_code='OTRO')))
for code in ('', 'OTRO', 'NARCISA DE JESUS'):
    guide = NS(company_id=co, destino=code, destino_codigo='NAJ', destino_id=route.destino_id)
    assert not selector._destination_matches(route, guide, NS(destination_id=NS(external_code='NAJ')))
print('OK: se utiliza transcash.guia.destino frente a ruta.destino_id.codigo')
