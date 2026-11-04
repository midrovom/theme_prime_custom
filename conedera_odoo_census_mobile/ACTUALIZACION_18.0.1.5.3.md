# Catastro PWA 18.0.1.5.3 – Arranque inmediato y compatible con datos anteriores

## Corrección
- La app dibuja su interfaz antes de abrir IndexedDB, sin dejar a los usuarios en pantalla bloqueante.
- Se abre la versión existente de la base (sin forzar actualización 1 a 2). Esto reduce conflictos con pestañas que usan versiones anteriores.
- Cuando la base existente es v1, los caches nuevos de productos y cotizaciones se guardan dentro de `meta`, sin modificar el esquema. Se conservan todos los registros previos y pendientes.
- Si el navegador impide abrir la base, se muestra la información en línea consultada desde Odoo, con aviso persistente. Para impedir pérdida de registros, las operaciones que precisan la cola local se bloquean hasta recuperar el almacenamiento.
- No se borra IndexedDB, la cola offline ni las operaciones pendientes. Service Worker actualizado a versión v9, separado de Odoo tradicional.

## Instalación
1. Respalde Odoo y actualice únicamente `conedera_odoo_census_mobile` a 18.0.1.5.3, sin desinstalarlo.
2. Reinicie el servicio y actualice el módulo. Cierre otras pestañas de Catastro y abra `/catastro/app?version=18.0.1.5.3`.
3. Verifique los pendientes offline antes de registrar visitas o cotizaciones. Si aparece modo en línea, cierre las otras pestañas y use Recuperar.
4. No borre datos del sitio ni desinstale la PWA si existen registros pendientes.

## Alcance de pruebas
Validaciones estáticas Python/XML/JavaScript y pruebas locales de arranque con almacenamiento de la versión anterior, además de fallo simulado del almacenamiento. La integración con el servidor de producción requiere validación en Odoo.
