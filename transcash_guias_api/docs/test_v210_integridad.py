from pathlib import Path
import ast
import xml.etree.ElementTree as ET
root=Path(__file__).resolve().parents[1]
controller=(root/'controllers/route_pwa_strict.py').read_text()
view=root/'views/route_pwa_identity_v27.xml'
assert 'destino_chofer' in controller and 'destino_transporte' in controller
assert 'destination_breakdown' in controller and 'resumen_destino' in controller
assert 'if guia.chofer_usuario_id:' in controller
assert 'guia.destino_id.id == master.id' in controller
assert 'No hay guías que cumplan simultáneamente' in view.read_text()
assert 'Guías del destino asignadas a otros choferes' in view.read_text()
ast.parse(controller)
ET.parse(view)
print('OK: Diagnóstico de intersecciones y datos alternativos disponibles')
