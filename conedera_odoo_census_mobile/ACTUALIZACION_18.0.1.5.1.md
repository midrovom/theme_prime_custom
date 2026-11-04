# Catastro App de Campo — actualización 18.0.1.5.1

## Problema corregido: «Cotizar» no visible

- Acceso principal **Cotizar ahora** en la pantalla inicial de catastros. Visible en teléfono y escritorio, sin depender de la barra inferior ni de estar dentro de un registro.
- En la ficha del catastro, **Cotizar** es visible incluso antes del cierre; la página de cotización explica por qué debe finalizar y protegerse primero, sin intentar saltar las reglas del servidor.
- Mensajes claros cuando falta el permiso `sale.order.create` o no hay catastros protegidos.
- En Más > **Actualizar interfaz PWA**, botón para descargar la nueva interfaz sin borrar IndexedDB ni operaciones pendientes.
- Los archivos CSS/JS incluyen una versión en la URL y el Service Worker usa una caché nueva y actualizaciones de red primero (con respaldo offline), evitando reutilizar el JavaScript anterior.

## Estado de la cotización y alcance

**Cotización rápida PWA:** permite crear un borrador `sale.order`, con cliente protegido, visita comercial opcional, productos, cantidades, referencia, lista e importes determinados por la lógica existente en Odoo. La cola offline conserva operaciones pendientes por usuario/empresa.

**Cotización completa (Odoo):** se añade una entrada visible al sistema completo para usar todas las operaciones y personalizaciones nativas mientras se replica la UI. El detalle de un borrador incluye «Abrir en Odoo» sobre ese mismo documento. Esta entrega no implementa en PWA los `onchange`, vistas, restricciones ni campos arbitrarios aportados por módulos de ventas que no se han facilitado. No sería seguro afirmar equivalencia funcional con extensiones aún desconocidas.

Para implementar todos esos campos y comportamientos dentro de la PWA se necesitan los ZIP de los módulos personalizados de `sale.order`, `sale.order.line` y las vistas de cotizaciones (o acceso técnico de lectura a ese código).

## Actualización segura

1. Respaldar base de datos y módulo, y sincronizar primero las operaciones pendientes de la PWA existente.
2. Sustituir **solo** `conedera_odoo_census_mobile` y actualizar `-u conedera_odoo_census_mobile` en staging; no desinstalar. El módulo base `conedera_odoo_census` se mantiene.
3. Reiniciar Odoo y abrir `/catastro/app` en línea. Comprobar en **Más** que figura la versión `18.0.1.5.1`.
4. Si el dispositivo sigue mostrando la versión antigua, usar **Más > Actualizar interfaz PWA**, sin pulsar «Borrar caché local». Las operaciones de IndexedDB no se borran.
5. Probar con usuario con/sin permisos de Ventas; validar que no se crea `sale.order` para catastro sin proteger; cotejar cotización con la vista nativa en la misma compañía.
6. Para una PWA instalada con el acceso técnico antiguo `/conedera/app`, abrir manualmente `/catastro/app` tras sincronizar operaciones pendientes; la URL anterior sigue redirigiendo.

## Nota de seguridad

Las reglas, precios, impuestos, compañía y el acceso a `sale.order` siguen verificados por Odoo. No se permite confirmar pedidos o modificarlos usando parámetros del navegador. El Service Worker solo controla `/catastro/`, nunca `/web`.

## Comportamiento de los dos modos

- **Cotizar ahora:** crea borrador rápido en la PWA. El usuario puede asociarlo a una visita, capturar referencia y líneas; el precio final lo calcula Odoo.
- **Cotización completa (Odoo):** abre directamente la acción de cotizaciones de Ventas, con todas las personalizaciones instaladas en esa base. Desde el detalle PWA también se puede abrir la cotización concreta, evitando perder la trazabilidad.
- Se conserva referencia y selección de visita al agregar varios productos, aun cuando la interfaz se actualice.

La pantalla nativa abierta desde la PWA **no equivale a una reimplementación completa dentro de la PWA**. Las extensiones arbitrarias no pueden replicarse con seguridad sin su código.
