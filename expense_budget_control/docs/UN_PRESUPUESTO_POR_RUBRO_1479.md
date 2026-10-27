# Versión 18.0.1.4.79: presupuesto único por rubro, empresa y año

- Cada presupuesto NUEVO necesita un Rubro en cabecera.
- En una empresa, año y rubro solo puede existir un presupuesto, independientemente de su estado (borrador, por aprobar, aprobado o rechazado).
- Se pueden crear presupuestos de diferentes rubros en el mismo año simultáneamente; ya no hace falta aprobar uno antes de registrar otro.
- Las cuentas de las líneas deben pertenecer al rubro seleccionado; la importación Excel valida lo mismo.
- Rubro aparece en la lista, formulario y filtros/grupos de búsqueda.
- Seguridad doble: verificación ORM y UNIQUE SQL, también para concurrencia.
- Históricos sin rubro en cabecera: post-migración rellena solo si todas las líneas corresponden a un rubro y no hay conflicto. Presupuestos históricos multirrubro permanecen íntegros (requieren revisión manual para adoptar la nueva regla).
- Si en datos antiguos ya existían cabeceras con la misma empresa/año/rubro, se detiene la actualización con IDs en el log sin borrar datos.
- La API de consumos, el cron, las reglas de gastos y los reportes PDF no se modifican.
