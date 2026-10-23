# v1.50 — Días desde última compra con estimación mensual (23/10/2026)

- En reposición se conservan las fechas exactas provenientes de la API y su edad calculada desde el documento cuando estén disponibles.
- Si existe únicamente último mes de compra YYYY-MM, se utiliza como referencia el **último día calendario de ese mes** y se calcula la diferencia de días con la fecha local actual del navegador. Los meses de 28, 29, 30 y 31 días se calculan correctamente, incluidos años bisiestos.
- Mes en curso: al ser todavía futura la fecha de fin de mes, se muestran **0 días (est.)** como referencia mínima, evitando valores negativos. Si por anomalía la fuente trae meses futuros, se muestra sin dato.
- La tabla distingue visualmente los días estimados con `(est.)` y explica el criterio en un tooltip y nota al pie. Se conserva `YYYY-MM (mes)` en última compra.
- Exportación Excel: los días estimados ahora aparecen también como números, bajo la columna `Días desde última compra (exactos o estimados)`. La fecha de compra indica si procede del mes consolidado o del día exacto.
- No se modifican filtros, cálculo de demanda, paginación, fórmulas de reposición, fuentes de datos, sincronización API, fotos, IA, permisos ni multiempresa.
- La antigüedad referencial de última compra NO equivale a la edad real de las unidades actualmente en stock, que requiere trazabilidad de lotes/Kardex.
