# Ajuste 1.4.74

En las proyecciones mensuales se muestran Rubro, Cuenta controlada, Código,
Centro de costo, Mes, Proyectado, Consumido, Disponible y Ejecución.
No se muestran Movimientos ERP ni Subcentro.

Consumido suma todos los gastos de **la empresa, la cuenta controlada (código
real del ERP), el centro de costo, el mes seleccionado y el año del presupuesto**.
Subcentro se conserva en los movimientos originales de Gastos reales por
trazabilidad, pero no participa en ninguna búsqueda ni en la conciliación.

El botón de consulta del presupuesto y los de Configuración API ERP se
muestran como **Actualizar costos**.

El PDF anual contiene una columna de Centro de costo; no incluye subcentro.

Una migración de actualización vuelve a conciliar los consumos importados
anteriormente sin modificar sus valores ni sus fechas. Si existen múltiples
líneas legadas de una misma cuenta/centro/mes con distintos subcentros, los
gastos se asignan a la primera línea creada para evitar una doble imputación;
las líneas presupuestarias existentes no se eliminan ni se fusionan.
