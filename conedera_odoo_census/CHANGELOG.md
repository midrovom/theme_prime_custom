# Changelog

## 18.0.1.4.0
- Bitácora móvil rediseñada como línea de tiempo Kanban que combina visitas y proformas.
- Botón **Ver bitácora completa** como respaldo para móvil/escritorio.
- Nuevo resumen por producto usando líneas reales de `sale.order`: cantidad proformada, documentos, importe, precio promedio neto ponderado, precio mínimo/máximo y última fecha.
- Historial por producto ordenado por fecha descendente, con cantidad, precio, descuento, precio neto y subtotal por proforma.
- Métricas de proformas agregadas también en la ficha estándar del producto (compañía actual), con botón al historial.
- Nuevo catastro: búsqueda por **RUC / Cédula** normalizada (ignora espacios, puntos y guiones).
- Si el cliente ya existe, el wizard muestra sus datos actuales y reutiliza el mismo `res.partner` para completar el catastro.
- Nueva verificación anti-duplicado por identificación normalizada.
- Reportes implementados con vistas SQL de solo lectura; no se duplican datos de ventas.
