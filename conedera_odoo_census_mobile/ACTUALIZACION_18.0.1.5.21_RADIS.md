# Catastro PWA 18.0.1.5.21 — Integración opcional Enviar a Radis

## Objetivo
Añadir **Enviar a Radis** en el detalle de una proforma ya guardada en Odoo.
Esta actualización NO crea un cliente HTTP nuevo, no copia credenciales al navegador,
y no modifica `stock_api_assing`: invoca su método existente
`sale.order.action_export_to_radis()` a través de un controlador PWA autenticado.

## Condiciones
- El módulo de origen `stock_api_assing` debe estar instalado y funcional.
- El usuario necesita permisos de escritura de Ventas, acceso al pedido por las reglas de Odoo,
  y pertenecer al grupo `stock_api_assing.group_quotes_restring`.
- El pedido debe pertenecer a la empresa activa, estar en estado `draft`, no estar marcado
  `export_send = E`, contener productos y tener una bodega.
- El botón no funciona sin conexión, ni se agrega a la cola offline.
- Si hay cambios concurrentes desde que se abrió la proforma, debe recargarse antes de enviar.
- El proceso original espera `success=true` y `order` en la respuesta de Radis;
  solo tras esa confirmación marca `export_send=E` y `state=async`.

## Límites de seguridad de los datos
El método original de stock_api_assing exporta todas las líneas de producto y transmite
`price_unit` y `negotiable_price`, pero no incluye `discount` de la línea ni modela
recompensas Loyalty como tales. La PWA **rechaza** el envío si detecta:
- un descuento porcentual de línea distinto de cero;
- una recompensa Loyalty como línea de producto;
- una proforma ya enviada o modificada por otra sesión.

Esto impide que la PWA envíe un importe equivocado a Radis. Para habilitar envíos con
promociones, primero debe acordarse con Radis un contrato que incluya descuento por
línea, subtotales e impuestos y ampliarse el método original. El control de esta PWA
no sustituye las validaciones del botón nativo de Odoo.

## Instalación
1. Respaldar PostgreSQL, filestore y directorio de módulos; sincronizar registros PWA pendientes.
2. Mantener `conedera_odoo_census` y `stock_api_assing` sin desinstalar.
3. Reemplazar solo la carpeta `conedera_odoo_census_mobile`, reiniciar todos los workers de Odoo.
4. Actualizar `conedera_odoo_census_mobile` desde Aplicaciones o `-u conedera_odoo_census_mobile`.
5. Abrir `/catastro/app?version=18.0.1.5.21`, entrar en Cotizar, seleccionar una proforma
   guardada en borrador y comprobar el bloque Radis.
6. En un entorno de pruebas, enviar una proforma SIN descuentos ni recompensas, verificar
   en Radis y en Odoo: `export_send=E`, `state=async`, no edición de líneas.

## Pruebas y riesgos adicionales
- Odoo es el único que invoca la API remota; nunca el navegador.
- Un error de red *después* de que Radis haya procesado una petición no demuestra que no
  se recibió: **no repetir automáticamente**. Verificar el estado en ambos sistemas.
- El método `stock_api_assing.action_export_to_radis` original oculta el botón por grupo,
  pero no verifica ese grupo dentro de la propia función. Esta PWA sí aplica la
  autorización en servidor; conviene endurecer también el método original.
- En `quotes_api.py` existe una rutina de exportación independiente; si se activa como
  cron, sus reglas pueden diferir de las del botón manual. Revisarla por separado.
- No se ha ejecutado este código en PostgreSQL/Odoo ni se ha hecho un envío real a Radis.
