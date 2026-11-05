# Catastro PWA 18.0.1.5.12 — cotizador de catálogo visual

- Catálogo visible desde el inicio al elegir la bodega, sin buscar SKU obligatoriamente. Muestra hasta 60 productos con stock físico positivo entre los primeros 250 SKU activos consultados; las búsquedas encuentran otros productos. No corresponde a un catálogo exhaustivo.
- Tarjetas móviles con fotografía ampliable, descripción legible, categoría, SKU, existencias, precio de lista y estimación con recargo de pago.
- Filtros de categorías entre los resultados actualmente cargados, orden por nombre, precio o stock. Las cantidades y la selección múltiple son las existentes.
- Barra flotante con cantidad de productos y total estimado referencial, botón «Revisar proforma», que lleva al carrito y a guardar. El importe oficial se obtiene al crear en Odoo.
- Se mantienen permisos, `negotiable_price`, Loyalty, recargos por línea, listas de precios, stock por bodega, cola offline, formularios nativos y ruta /catastro/app.
- Sin modificación de modelos de negocio ni migración de almacenamiento.

## Pruebas antes de producción

1. Actualizar el módulo y comprobar versión 18.0.1.5.12.
2. En móvil, elegir una bodega y verificar que cargan los primeros productos con stock; buscar un SKU fuera de la primera página.
3. Confirmar fotos, categorías, selección múltiple, total estimado y guardado de borrador.
4. Con perfil Tienda, confirmar que no aparece `negotiable_price` y que Loyalty sigue disponible.
5. Verificar recargo, campos de auditoría e impuestos reales en el pedido Odoo, y probar datos offline pendientes.
