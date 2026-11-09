# Promociones Loyalty por bodega — Odoo 18

Módulo nuevo e independiente. **No modifica** `sale_loyalty`, `catastro_pwa_loyalty_bridge`, `stock_api_assing` ni `conedera_odoo_census_mobile`.

## Configuración

Ventas → Productos → Descuentos y fidelización → abrir un programa → **Bodegas donde aplica (Ventas / PWA)**. Seleccione Bodega A y Bodega B, por ejemplo. La promoción será aplicable a ambas y no a Bodega C.

Si deja el campo vacío, la promoción continúa funcionando en **todas las bodegas**, preservando los programas existentes. Se valida que las bodegas pertenezcan a la empresa del programa cuando esté definida.

## Funcionalidad

* Restringe los programas mediante los dominios nativos de Odoo 18 (`_get_program_domain` y `_get_trigger_domain`). Así también filtra los códigos promocionales y las opciones que consulta la PWA.
* Al guardar un **borrador** con otra bodega, vuelve a comprobar la elegibilidad; elimina los descuentos anteriores no válidos y los reaplica únicamente cuando corresponde. La comprobación se hace en Odoo, no solo ocultando una oferta en JavaScript.
* Una promoción aplicable en dos bodegas conserva las mismas reglas, fechas, límites y productos que haya configurado en Loyalty.
* No amplía bodegas autorizadas para cotizar: esos permisos siguen controlados por el módulo PWA.
* No cambia promociones de Punto de Venta (POS): el alcance es Ventas y Catastro PWA.

## Dependencias

`catastro_pwa_loyalty_bridge` 18.0.1.0.2, `sale_loyalty`, `sale_stock` y la PWA ya instalada.

## Instalación

1. Respalde la base, filestore y directorio de módulos.
2. Conserve los módulos existentes; agregue `catastro_pwa_loyalty_warehouse` a `addons_path`.
3. Reinicie los procesos de Odoo, actualice lista de aplicaciones e instale el nuevo módulo.
4. Configure las bodegas en los programas de promoción y pruebe una cotización en cada bodega.

## Pruebas recomendadas en servidor

* Promo válida en A/B, no en C; modificar bodega de A a C quita descuentos anteriores.
* El precio de la tarjeta y el resumen reflejan el cambio después de consultar al servidor.
* El código promocional también se rechaza fuera de su bodega.
* Verificar edición/duplicación de proforma y envío Radis por separado.
* Confirmar impuestos y descuentos en el XML de prueba de factura electrónica SRI antes de producción.

Las pruebas estáticas del paquete no equivalen a una prueba ejecutada contra PostgreSQL y la instalación real de Odoo.

Cuando un programa pertenece a una compañía matriz, se permiten bodegas de esa matriz o sus filiales directas, en consonancia con el ámbito de compañías que admite `sale_loyalty` en Odoo 18.
