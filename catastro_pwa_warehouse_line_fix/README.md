# Catastro PWA – Bodega en líneas de proformas

**Módulo:** `catastro_pwa_warehouse_line_fix`  
**Versión:** 18.0.1.0.0  
**Requiere:** `conedera_odoo_census_mobile`, `stock_api_assing` (y sus dependencias).

## Problema corregido

En **Pendientes** aparece el error PostgreSQL:

`null value in column "warehouse_id" of relation "sale_order_line" violates not-null constraint`

La PWA selecciona y valida la bodega, pero ciertas versiones construyen los
comandos `order_line` sin `warehouse_id`. Durante `sale.order.create()` anidado,
las personalizaciones pueden intentar asignarla demasiado tarde.

## Cambio

- Al crear un pedido con `warehouse_id`, completa esa misma bodega en cada nueva línea que no tenga otra ya especificada.
- Al agregar líneas mediante `sale.order.write()`, completa la bodega del pedido.
- Al crear una línea suelta con `order_id`, usa la bodega de la orden si falta.
- Respeta `warehouse_id` explícito por línea y no altera la elección del usuario.
- No elimina operaciones offline, no cambia el stock, no modifica el módulo `stock_api_assing` ni los nombres de rutas de la PWA.
- No añade columnas nuevas a PostgreSQL ni depende de la versión exacta del frontend.

## Instalación segura

1. Hacer respaldo de PostgreSQL, filestore y addons.
2. **Mantener la PWA actual** y `stock_api_assing` sin reemplazar ni desinstalar.
3. Descomprimir la carpeta `catastro_pwa_warehouse_line_fix` en un directorio de `addons_path`.
4. Reiniciar **todos** los procesos de Odoo, actualizar la lista de Aplicaciones e instalar `Catastro PWA - Bodega en líneas de proformas`.
5. Cerrar otras pestañas de la PWA. En **Pendientes**, verificar la bodega elegida, y pulsar **Sincronizar ahora** una sola vez.
6. Abrir la proforma generada y revisar bodega por producto, precio, impuesto, descuentos y stock; solo despues enviar a Radis.

**No eliminar la cola local, IndexedDB ni los datos del sitio** antes de recuperar las operaciones pendientes.

## Alcance y consideraciones

El complemento resuelve el campo nulo antes de que PostgreSQL inserte la línea.
No sustituye las reglas de existencia de `stock_api_assing`: el original valida
los quants en `lot_stock_id`, que pueden diferir de la suma en ubicaciones hijas.

Este paquete ha sido validado con pruebas estaticas y unitarias, pero **no ha
sido instalado ni probado con PostgreSQL en el servidor del usuario**.

Si vuelve a producirse un error de `warehouse_id` tras la instalacion, recopilar
el nuevo traceback completo del servidor (podria venir de un modulo distinto o
de la generacion de recompensas Loyalty).
