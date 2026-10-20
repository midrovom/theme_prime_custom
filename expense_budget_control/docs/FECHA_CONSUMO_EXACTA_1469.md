# v1.4.69 – Fecha de consumo ERP exacta

- **Proyecciones mensuales → Fecha de consumo** es un selector de día, mes y año. El usuario deja de escoger manualmente una categoría de mes.
- Para `Fecha: "nov 25 2023 12:00:00:000"`, se usa el día `25/11/2023`; la hora no se usa porque Odoo registra el gasto en `fields.Date`.
- Se suman exclusivamente gastos con la misma **cuenta (Codigo), centro (Centro), subcentro (Subcentro)** y **fecha completa**. Si el usuario no escoge subcentro, se suman los subcentros aplicables a esa fecha, igual que antes.
- El `month` interno se deriva automáticamente de la fecha y queda disponible para el dashboard, comparativos, informes y agrupaciones mensuales.
- **Sin migración destructiva:** para líneas creadas antes de v1.4.69 donde `consumption_date` está vacío, el cálculo sigue siendo **mensual**. Al escoger una fecha en un presupuesto en borrador, se reconcilian los gastos existentes y se comprueba el día exacto.
- El año seleccionado debe coincidir con el año del encabezado del presupuesto. Se permite una cuenta con varios días dentro del mismo mes, pero no se permite duplicar exactamente la misma cuenta/centro/subcentro/día.
- La API `getconsumosgastos/2`, la tarea cron, los reportes y los movimientos históricos no se modifican. Solo cambia la identificación de la proyección y la imputación por fecha.
