# Inventario Inteligente v1.42 — Corrección de gramática SQL

## Problema
Al cargar el módulo, el analizador SQL puede producir `GrammarError: Rule 'SIGNED_NUMBER' used but not defined (in rule scalar)` porque la importación de terminales desde la gramática auxiliar de la librería incorporada no se resuelve en algunos entornos.

## Solución
- Se definen `SIGNED_NUMBER`, `INT` y `WS` **dentro de la propia gramática SQL**, sin buscar archivos de gramática externos.
- Se mantienen las importaciones **relativas** de la librería `vendor_lark` corregidas en v1.41.
- No cambia el ejecutor SQL seguro, rutas web, modelos, dashboards, estilos móviles ni APIs.

## Actualización
1. Respaldar y reemplazar **completamente** la carpeta del módulo `transcash_inventory` por la del ZIP (sin crear una carpeta anidada adicional).
2. Reiniciar todos los trabajadores de Odoo; actualizar el módulo desde Aplicaciones cuando Odoo haya arrancado. No desinstalar ni borrar datos.
3. Si vuelve a aparecer el error, comprobar la versión del `__manifest__.py` en el directorio que figura en el traceback, y verificar que `services/ai_semantic_sql.py` no tiene líneas `%import common.`.
