# Catastro - App de Campo 18.0.1.5.7

## Cotizaciones rápidas con control por bodega

- Muestra **total a precio de lista** y **total a precio negociado** multiplicando cantidades y precios unitarios.
- Cuando no se introduce `negotiable_price` en una línea, el total negociado usa el precio nativo de la lista para esa línea. No se crea ni se modifica otro campo de precio en Odoo.
- Ambos importes son referenciales, antes de impuestos, y se recalculan al cambiar cantidades o lista de precios. El total definitivo lo calcula `sale.order` en el servidor.
- Para buscar productos se debe seleccionar una **bodega**. Si hay una sola, se preselecciona.
- Solo muestra variantes con `qty_available > 0` en la bodega y compañía activas. Las variantes de servicio y las que no tienen existencias quedan fuera de la búsqueda rápida.
- Antes de guardar el borrador, el servidor Odoo revalida **producto, bodega, cantidad** y que el pedido final conserve esa bodega. La validación se realiza también para operaciones offline pendientes **al sincronizar**.
- El stock a mano no constituye una reserva de inventario y puede variar tras guardar una cotización.

## Requisitos y compatibilidad

Necesita Inventario y la integración de almacén en Ventas (campo `sale.order.warehouse_id`, habitualmente provisto por `sale_stock`). El módulo PWA no crea modelos de inventario ni altera reglas de stock. No se realizó una migración de IndexedDB.

## Pruebas en Odoo

1. Definir dos bodegas: producto A con 5 en Bodega Norte y 0 en Bodega Sur; verificar que A solo aparece en Norte.
2. Agregar A con cantidad 3 y precio lista 10, negociado 8: mostrar 30 a lista y 24 negociado, antes de impuestos.
3. Agregar producto B con cantidad 2 sin precio negociado; total negociado debe incluir su precio nativo.
4. Intentar guardar 6 de A en Norte o 1 de A en Sur: Odoo debe rechazar el guardado.
5. Cambiar la bodega de una cotización en curso y comprobar que el stock se consulta nuevamente antes de guardar.
6. Crear una operación offline con stock cacheado: al sincronizar se revalida el inventario y se informa si ya no es suficiente.
7. Confirmar que `negotiable_price` permanece en las líneas y que tus personalizaciones de Ventas calculan el precio oficial.
