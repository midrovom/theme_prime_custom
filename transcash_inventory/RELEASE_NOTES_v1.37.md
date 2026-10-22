# Inventario Inteligente 18.0.1.37.0 — Consultas en lenguaje natural de múltiples indicadores

## Motor de consulta integrado con Odoo
- El catálogo dinámico se obtiene de los modelos de Odoo: `transcash.inventory.fact.product`, `fact.sale`, `fact.purchase`, `fact.supplier.purchase` y `fact.stock` (nombres completos documentados en `services/ai_schema.py`).
- ChatGPT recibe campos permitidos, sus relaciones, dimensiones, etiquetas comerciales y fórmulas. Devuelve un **plan estructurado**; el servidor Odoo compila el `SELECT` con listas blancas y parámetros, limitando empresa y versión. No se ejecuta SQL arbitrario de la IA.
- Se admiten hasta 16 columnas de análisis por SKU en el plan general, incluyendo categoría, marca, formato, proveedor, costo y precio de catálogo, ventas, compras, cantidades, costo de ventas, utilidad y margen bruto, stock y últimos meses de movimiento.
- Las consultas rápidas con filtros de stock admiten ahora compras USD, ventas USD, cantidades, costo de ventas, utilidad bruta, margen bruto y precio promedio, junto con el stock físico.
- La rentabilidad solicitada sin calificativo muestra `utilidad = ventas netas - costo de ventas` y `margen = 100 × utilidad / ventas`. Si ventas es cero, margen se muestra vacío.
- Importes de compras/ventas proceden del período filtrado; stock físico corresponde al último corte, y las últimas compras/ventas son meses YYYY-MM de todo el historial disponible.
- Las tablas y sus exportaciones XLSX mantienen la selección de columnas de la consulta. El SQL se guarda solamente en bitácora administrativa.
- No se altera el adaptador API Administrator, la persistencia multiempresa, las fotografías ni los dashboards existentes.

## Ejemplos

1. «Muéstrame los porcelanatos con stock mayor a 10 y menor a 100, cantidad comprada, cantidad vendida y rentabilidad, ordenados por utilidad descendente».
2. «Ventas, costo de ventas, utilidad y margen por marca para el formato 60×120 en los últimos 6 meses».
3. «Top 10 SKU con mayor utilidad bruta, mostrando stock, última compra, última venta, proveedor, marca y formato».

## Alcance y limitaciones
- Sin trazabilidad de lotes no se atribuye la utilidad a un proveedor real de movimiento; el proveedor del catálogo es la referencia para la rentabilidad de cartera.
- No hay rentabilidad neta, rotación histórica real ni GMROI con el conjunto de datos actual.
- Se respetan `company_id` y `snapshot_id` del usuario. Recomendado probar en instancia de staging antes de producción.
