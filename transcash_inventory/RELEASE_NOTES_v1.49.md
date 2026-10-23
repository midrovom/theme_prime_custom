# v1.49 — Reposición paginada e historial de movimientos (22/10/2026)

- El simulador ya no oculta los candidatos después del producto 50: incluye paginación de 25/50/100 SKU, conservación de filtros y fotografías solo de la página visible.
- Demanda diaria = cantidad neta vendida en el período / días efectivos; por defecto últimos 12 meses cerrados.
- Agrega última compra, cantidad de última compra, última venta, cantidad de última venta, y días desde última compra **cuando la API aporta fecha exacta**.
- Si solo hay acumulados mensuales, se muestra el último mes con compra/venta (YYYY-MM, mes) y el total mensual, nunca un día ni una cantidad de factura fabricados.
- Campos opcionales aceptados en las fuentes de API: `fecha_ultima_compra`, `cantidad_ultima_compra`, `fecha_ultima_venta`, `cantidad_ultima_venta` (fecha ISO YYYY-MM-DD o DD/MM/YYYY). Se pueden incluir en getproductosinvt, y para cada movimiento en getcomprasinvt/getventasinvt.
- Las columnas adicionales se exportan completas a Excel con todos los candidatos, independientemente de la página actual.
- Fingerprint de versiones incluye los campos exactos optativos, cuando se encuentran, para que futuras sincronizaciones actualicen las fechas aunque los consolidados mensuales no cambien.
- No se modifica la heurística ni las fórmulas de reposición, ni fotografías, IA, permisos o endpoints.
- Los días desde la compra NO miden la edad efectiva del stock por lotes, requieren fechas documentales.
