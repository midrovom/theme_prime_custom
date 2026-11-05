# Catastro PWA 18.0.1.5.19 — Promociones por producto / fotos PDF / WhatsApp

## Instalación

1. Respalde base de datos, filestore y módulos. Sincronice operaciones PWA pendientes.
2. Sustituya el directorio `conedera_odoo_census_mobile` por la versión 18.0.1.5.19.
3. Instale o actualice **además** `catastro_pwa_loyalty_bridge` a 18.0.1.0.2.
   Este complemento necesita `sale_loyalty` y añade los campos de auditoría de promociones por línea.
4. Reinicie todos los workers y actualice primero `conedera_odoo_census_mobile`; luego `catastro_pwa_loyalty_bridge`.
5. Abra `/catastro/app?version=18.0.1.5.19` y compruebe las dos versiones en Aplicaciones.

## Promociones representables como descuento por línea

- Programas automáticos de **Promociones** aplicables al pedido actual.
- Recompensas de tipo **Descuento, Porcentaje, Productos específicos**.
- Sin tope monetario y sin tarjetas nominativas, monederos o canje de puntos.
- Elegibilidad recalculada a partir del motor de reglas nativo: cliente, compañía,
  lista de precios, fecha, cantidades mínimas, importes mínimos, producto y categoría.
- Se guarda en `sale.order.line.discount`; la marca y el descuento previo quedan en
  `catastro_pwa_promo_reward_id` y `catastro_pwa_promo_base_discount`.
- Si deja de cumplir los requisitos de la promoción al editar o confirmar, se restaura
  el descuento anterior y se elimina la promoción.
- No se crean productos genéricos ni líneas de recargo para representar la promoción.

**No se convierten automáticamente cupones con redención, tarjetas regalo, monederos,
productos gratis, montos fijos, recompensas globales o descuentos topados.** Son
operaciones con otras reglas contables y de puntos; se mantienen en Odoo para una
integración fiscal específica posterior. No se debe afirmar compatibilidad integral SRI
sin validar el XML emitido por la localización ecuatoriana instalada.

## Fotografías en PDF

Se hereda `sale.report_saleorder_document` con una miniatura opcional de 56 px por producto
si el registro posee imagen. No se sustituye la plantilla original de QWeb.
Si existen modificaciones de terceros, comprobar prioridad / XPath en una base de ensayo.

## WhatsApp

`navigator.share` / compartir archivos exige HTTPS, compatibilidad del navegador
móvil y selección manual del destino. `wa.me` abre un chat pero no adjunta PDFs.
En HTTP la PWA permite descargar el documento y abrir el chat para adjuntarlo a mano.
Para HTTPS, configure un dominio, certificado TLS y reverse proxy (por ejemplo nginx)
con `proxy_mode=True` en Odoo y URL pública HTTPS. No publique una ruta anónima a PDFs.
Para envío *automático* al número desde el servidor es necesaria una integración
WhatsApp Business API autorizada y sus credenciales; no está incluida aquí.

## Pruebas de aceptación en servidor real

- Crear cotización con dos productos que habiliten una promoción, verificar `discount`.
- Quitar uno y comprobar que pierde elegibilidad y se revierte el descuento.
- Editar un borrador previamente guardado; verificar precio base y recargo no duplicados.
- Confirmar y generar factura de prueba: inspeccionar `account.move.line.discount`
  y XML SRI de la localización instalada; verificar impuestos y redondeos.
- Exportar PDF con/sin foto, comprobar compatibilidad con plantilla personalizada.
- Verificar compartir desde HTTPS/iOS/Android y descarga manual sobre HTTP.

**No se probó contra su PostgreSQL ni personalizaciones de ventas en producción.**
