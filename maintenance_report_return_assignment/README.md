# Maintenance Report — Asignación de equipos a bodega (Odoo 18)

**Versión:** `18.0.1.6.0`. Es una actualización del mismo módulo
`maintenance_report_return_assignment`, NO un nuevo complemento.

## Funcionalidad

- **Empleados**: casilla **Es bodega** (`hr.employee.es_bodega`), justo debajo
  de Departamento. Marcar Bodega Sistema (o cualquier empleado válido).
- **Ficha del equipo**: botón inteligente **Asignar a bodega**. Abre una ventana
  pequeña independiente de los wizards de entrega/devolución/uniformes.
- **Selector**: `hr.employee`, con filtro Es bodega = Sí y misma empresa
  (también admite empleados sin empresa). No usa Contactos ni crea empleados.
- **Confirmación**: cambia `maintenance.equipment.employee_id` al destino.
  Valida de nuevo en servidor la casilla y empresa para evitar saltarse el
  filtro desde una llamada externa.
- **Auditoría**: guarda el empleado anterior en
  `empleado_devolucion_anterior_id`, el usuario que hizo el movimiento en
  `bodega_asignado_por_id`, y la fecha/hora en `bodega_asignacion_fecha`.
  Los tres campos se ven en la ficha del equipo. Se deja también nota en el
  chatter del equipo con el movimiento y el usuario que lo hizo.
- **Actas**: el wizard original no recibe nuevos campos ni modifica la
  asignación. Los PDFs de devolución conservan al empleado que devolvió el
  equipo cuando éste está asignado a una bodega, sin mostrar el nombre
  de la bodega como devolvente.
- **Historial**: los campos muestran el *último* movimiento; la nota del
  chatter permite consultar los anteriores cuando se hacen varias asignaciones.

## Flujo recomendado

1. En **Empleados**, abrir **Bodega Sistema** y marcar **Es bodega**.
2. En Equipos, generar el acta de devolución como de costumbre.
3. Abrir el equipo y pulsar **Asignar a bodega**; seleccionar **Bodega Sistema**
   y confirmar.
4. Verificar que **Empleado** ahora indica Bodega Sistema y que
   **Registrado por** muestra el usuario que confirmó el traslado.

**Nota de impresión:** si se necesita reimprimir el acta después del traslado,
la plantilla utiliza el campo Empleado anterior para identificar a quien devolvió
el equipo.

## Actualización

Reemplazar la carpeta `maintenance_report_return_assignment` del addons-path,
reiniciar Odoo y actualizar el mismo módulo desde Aplicaciones o ejecutar
`-u maintenance_report_return_assignment`. Dependencias: `hr_maintenance`,
`maintenance_report`, `maintenance_report_unifor`.

Hay una migración que elimina la antigua vista que agregaba el campo al wizard.
La información de equipos, contactos y empleados no se elimina.

**Verificación:** se han comprobado sintaxis Python, XML, estructura del ZIP y
la lógica de asignación con pruebas locales. Probar en una base de pruebas
Odoo 18 antes de llevar a producción.
