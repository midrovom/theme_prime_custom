# TRANSCASH Inventario Inteligente v1.41 — Corrección de importaciones en Odoo

## Causa
La versión v1.40 importaba Lark mediante `from transcash_inventory.vendor_lark ...`. Cuando Odoo carga la carpeta como subpaquete (por ejemplo `odoo.addons.theme_prime_custom.transcash_inventory`), el nombre absoluto `transcash_inventory` no existe en `sys.path`. La importación detiene el inicio de Odoo.

## Corrección
- Cambia a importaciones relativas al paquete del módulo: `from ..vendor_lark import Lark, Tree, Token`.
- Corrige los imports absolutos remanentes dentro de `vendor_lark` y de sus analizadores LALR.
- Mantiene intactos modelos, rutas HTTP, analítica SQL, assets y diseño móvil de v1.40.
- Versión del manifiesto: `18.0.1.41.0`.

## Actualización
Sustituir la carpeta `transcash_inventory` sin eliminar datos, reiniciar el servicio Odoo y actualizar la aplicación. No desinstalar. Validar en una base de pruebas antes de usar en producción.
