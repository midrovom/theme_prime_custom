# Inventario Inteligente TRANSCASH v1.33 — Ranking de stock con últimos movimientos

Base: v1.32. Cambios específicos, sin modificaciones de modelos PostgreSQL.

## Consulta soportada

> Muéstrame el top 10 de productos con mayor cantidad física de stock, ordenados de mayor a menor. Incluye SKU, descripción completa, stock, última compra y última venta.

## SQL controlado
- Compilador de planes autorizado: `metric=stock_unidades`, `group_by=sku`, `top_n=10`, `orden=desc`.
- Columnas seleccionables en `metrics`: `descripcion`, `stock_unidades`, `ultima_compra`, `ultima_venta`.
- Los últimos movimientos se calculan usando `MAX(mes)` en `fact.purchase` y `fact.sale`.
- Meses en formato `YYYY-MM`: **no** son fechas exactas de factura. Se obtienen de todo el historial de la versión, independientemente del período activo de ventas.
- Solo se consideran meses con cantidad comprada/vendida positiva; un SKU sin movimientos conserva fecha vacía.
- No se combinan compras y ventas detalle directamente, evitando multiplicaciones de importes.
- Los filtros de empresa y versión se aplican en cada subconsulta.
- Si ChatGPT intenta proponer un ranking distinto, el servidor impone la ordenación física por stock cuando la petición pide el top por cantidad.
- La tabla visible y el Excel incluyen las cuatro columnas solicitadas más el SKU.

## Instalación
1. Respaldar la base de datos y el filestore.
2. Sustituir íntegra la carpeta `transcash_inventory` por la nueva versión.
3. Reiniciar los procesos Odoo y actualizar el módulo en Aplicaciones, sin desinstalarlo.
4. Cerrar y recargar el navegador. La pantalla HTML usa recursos `dashboard_v133.js` y `18.0.1.33.0` para evitar JavaScript almacenado en caché.
5. Probar una consulta como usuario con permiso IA en la empresa correcta.

La conexión con tu instancia Odoo 18 y la API Key no se ha probado desde este entorno. No es necesario recargar el inventario para consultar meses de compra y venta existentes.
