# Versión 1.4.73: cálculo de Consumido por mes

En Proyecciones mensuales se selecciona **Mes** (Enero-Diciembre), no una fecha exacta.
El **Año** es el año del presupuesto. El importe **Consumido** suma los movimientos
registrados del primer al último día de ese mes, siempre que correspondan a:

- `expense.budget.account.code` = `Codigo` del ERP;
- `expense.budget.cost.center.code` = `Centro` (sin espacios sobrantes);
- `expense.budget.line.subcenter_code` = `Subcentro` (sin espacios sobrantes);
- mes y año de `Fecha` = período de la línea.

Si una combinación tiene varios movimientos en ese mes, el sistema muestra **una única
cantidad mensual total**, resultado de sumar los `Valor` correspondientes. Si no hay
movimientos coincidentes el valor es cero.

No se elimina `consumption_date` de PostgreSQL para preservar históricos anteriores,
pero deja de formar parte del cálculo, la conciliación y la importación. Cuando se
edita el Mes de una línea antigua, `consumption_date` se limpia automáticamente.

No se modifican los importes proyectados; el cálculo utiliza gastos ya importados y
consulta la API al crear o cambiar una proyección siguiendo las reglas de caché previas.

Si la base contiene varias proyecciones antiguas para una **misma cuenta/centro/
subcentro/mes** pero con distintas fechas, revisarlas antes de consolidarlas:
la versión nueva impide crear duplicados de período, pero **no fusiona ni borra
automáticamente los presupuestos históricos**. La conciliación usa la primera
línea del mismo período cuando existen duplicados históricos.
