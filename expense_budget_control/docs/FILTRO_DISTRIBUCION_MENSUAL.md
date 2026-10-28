# Fila de captura para proyecciones mensuales — 18.0.1.4.87

En el formulario de Presupuestos anuales, el bloque **Agregar proyecciones por meses** presenta una sola fila:

- **Cuenta controlada**: limitada al rubro y empresa del presupuesto.
- **Centro de costo**: limitado a la empresa.
- **Meses**: selección múltiple por nombre (Enero, Febrero, etc.); excluye meses ya presupuestados de la misma cuenta, centro y año, y meses protegidos por aprobación.
- **Presupuesto anual**: importe a repartir entre los meses elegidos.
- **Agregar**: crea proyecciones mensuales debajo y restablece la fila a valores vacíos.

Ejemplo: Agua / Quito / Enero-Diciembre / $1.200 crea 12 líneas con proyectado $100 cada una.

## Compatibilidad

Se reutiliza el asistente existente `expense.budget.quick.add.wizard` para distribuir importes, mantener los objetivos anuales y respetar los controles de aprobación y de duplicación. Los objetivos anteriores pueden consultarse o ajustarse (si no están protegidos) en la pestaña **Distribuciones registradas**. Las operaciones de actualización de consumos, reportes y sincronización API permanecen inalteradas.

Los presupuestos deben guardarse primero para contar con un registro sobre el que generar líneas. Los meses y el importe pueden seleccionarse dentro de un presupuesto en borrador o aprobado, pero no durante la aprobación pendiente.
