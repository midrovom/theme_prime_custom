# Catastro PWA 18.0.1.5.20 — precio inmediato con promoción e impuestos

## Cambio
Al elegir una promoción porcentual por producto, la tarjeta, las alternativas de forma de pago, el resumen fijo y la revisión de la proforma muestran el precio unitario **con descuento e impuestos incluidos**, calculado por el servidor Odoo. La elección se hace también desde la tarjeta de un producto agregado.

El endpoint `quote/promotions/preview` calcula importes por cada oferta válida, utilizando la lista de precios, posición fiscal e impuestos del cliente y la bodega y formas de pago actuales. No crea pedidos. Los descuentos se materializan en `sale.order.line.discount` al guardar mediante el módulo Loyalty ya existente. Si cambia la cantidad, un producto o la bodega, no se presenta un importe promocional obsoleto como válido.

## Instalación
Actualizar SOLO `conedera_odoo_census_mobile` a 18.0.1.5.20, con `catastro_pwa_loyalty_bridge` en versión 18.0.1.0.2 instalada para elegir las ofertas por producto. Reiniciar todos los workers, actualizar módulo desde Aplicaciones, abrir `/catastro/app?version=18.0.1.5.20`. No eliminar datos offline de la PWA.

## Pruebas necesarias en Odoo real
1. Seleccionar producto con promoción y comprobar cambio inmediato de precio con IVA.
2. Cambiar forma de pago, cantidad, eliminar condición y comprobar reversión.
3. Revisar y guardar: contrastar importe de la tarjeta con `sale.order.line.price_total` e impuestos.
4. Verificar promociones en consumidores finales y ventas con posiciones fiscales particulares, descuentos nativos y negociación.
