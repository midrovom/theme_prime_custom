"""Validación estática del complemento v2.12 (ejecutar con python3)."""
import ast
from pathlib import Path
from lxml import etree

MODULE = Path(__file__).resolve().parents[1]

def run():
    manifest = ast.literal_eval((MODULE / '__manifest__.py').read_text())
    assert tuple(int(v) for v in manifest['version'].split('.')) >= (18, 0, 2, 12, 0)
    for resource in manifest['data']:
        assert (MODULE / resource).is_file(), resource
    for path in MODULE.rglob('*.py'):
        compile(path.read_bytes(), str(path), 'exec')
    for path in MODULE.rglob('*.xml'):
        etree.parse(str(path))
    model = (MODULE / 'models/route_traceability.py').read_text()
    selector = (MODULE / 'controllers/route_pwa_strict.py').read_text()
    views = (MODULE / 'views/route_traceability_views.xml').read_text()
    assert 'action_tc_ver_hoja_ruta' in model
    assert 'action_tc_ver_embarque' in model
    assert 'action_tc_guias_del_chofer' in model
    assert "'domain': domain" in model
    assert 'def _driver_guide_overview' in selector
    assert "'company_id', '=', ruta.company_id.id" in selector
    assert 'if not (driver_ok or same_record or same_document)' in selector
    assert "<field name=\"domain\">[]</field>" in views
    assert 'tc_disponibles_v212' in views
    assert 'tc_asignadas_v212' in views
    print('OK: manifest, Python, XML, trazabilidad y aislamiento de conductor')

if __name__ == '__main__':
    run()
