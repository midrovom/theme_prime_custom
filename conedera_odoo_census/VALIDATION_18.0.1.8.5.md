# Validación estática — 18.0.1.8.5

Checks OK: 10
Errores: 0

## OK
- Root __init__.py imports only models
- No malformed _init_.py file
- Manifest version 18.0.1.8.5
- Manifest data/assets paths exist
- 49 Python files compile
- All direct relative module imports resolve to files/packages
- models/__init__.py imports resolve
- 20 XML files parse; 127 explicit IDs unique
- Compatibility bootstrap covers legacy flattened model imports
- Latest 1.8.4 DB migration remains non-destructive

## Diagnóstico del traceback
- El ZIP 18.0.1.8.4 entregado tenía un `__init__.py` raíz correcto (`from . import models`).
- El traceback del servidor muestra un inicializador distinto que intenta importar `crm_team` desde la raíz.
- Esto indica una carpeta instalada mezclada/antigua o una copia que no reemplazó completamente el addon.
- La 18.0.1.8.5 añade un bootstrap de compatibilidad, pero se exige reemplazo completo de la carpeta instalada.

## Alcance
- Validación estática. No sustituye el import real dentro de Odoo 18 + PostgreSQL.
