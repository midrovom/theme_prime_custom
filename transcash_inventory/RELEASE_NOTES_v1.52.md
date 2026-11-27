# TRANSCASH Inventario Inteligente — 18.0.1.52.0

## Bodega · stock (multiselección)
- El filtro ahora tiene un desplegable con búsqueda y casillas de selección.
- Se pueden elegir una, dos o más bodegas; el botón **Todas las bodegas** elimina la restricción.
- El stock positivo, las unidades, los valores de inventario, los SKU que tienen existencias,
  los indicadores y las tablas por bodega usan SOLO las bodegas seleccionadas.
- La ficha del producto presenta las ubicaciones elegidas, no las demás.
- El botón de una barra de bodega selecciona esa bodega y actualiza el dashboard.
- El escenario de reposición sigue deshabilitado con filtro de bodega porque la fuente de
  ventas/compras solo tiene movimientos corporativos, no ventas por ubicación.
- La información de ventas/compras del dashboard es **corporativa para los SKU de las
  bodegas elegidas**; la selección no inventa ventas ni compras históricas por bodega.

## Favoritos / filtros guardados
- Menú **Favoritos** dentro de Filtros de análisis, estilo guardado de búsquedas de Odoo.
- Guardar, recuperar, reemplazar por nombre y eliminar filtros propios.
- Marcar como predeterminado al abrir el tablero y opcionalmente compartir con usuarios
  autorizados de la misma empresa.
- Guardados en PostgreSQL mediante el modelo `transcash.inventory.saved.filter`
  (persisten entre equipos/sesiones), con permisos de lectura y propiedad.
- Las bodegas se guardan por nombre para tolerar cambios de orden del catálogo al
  sincronizar. Si desaparece una bodega del inventario, el favorito avisa y NO amplía
  la búsqueda silenciosamente a todas las bodegas.
- Los favoritos guardan período, categoría, marca, formato, proveedor, bodegas, búsqueda,
  filtro ABC y de acción. No alteran la información fuente.

## Actualización
Actualiza el módulo existente a la versión `18.0.1.52.0` (no instalar junto al anterior),
reinicia Odoo y fuerza una recarga del navegador para obtener `dashboard_v152.js/css`.
No requiere volver a importar o sincronizar inventario.
