# Maintenance Report — Entrega y devolución de equipos con historial (Odoo 18)

**Módulo:** `maintenance_report_return_assignment`  
**Versión:** `18.0.1.15.0`  
**Dependencias:** `hr_maintenance`, `maintenance_report`, `maintenance_report_unifor`.

## Acta de entrega: dos comportamientos independientes

- **Usado por = Empleado:** se mantiene el reporte y el flujo original de entrega, con la firma del empleado al que está asignado el equipo.
- **Usado por = Departamento:** el PDF muestra al departamento responsable y una línea de firma **RECIBÍ CONFORME** para cada empleado activo del departamento. No asigna los equipos a empleados específicos.
- Si se seleccionan varios equipos departamentales para una misma acta, todos deben pertenecer al mismo departamento. La entrega de uniformes no se altera.

## Acta de devolución: flujos diferentes

| Función | Equipos usados por Empleado | Equipos usados por Departamento |
|---|---|---|
| **Empleado actual** | Autocompletado, solo lectura | Seleccionable entre empleados del departamento del equipo |
| **Bodega de devolución** | Obligatoria, solo empleados con **Es bodega** | **Oculta**, no se exige ni se transfiere a bodega |
| **Equipo entregado a (empleado)** | Empleados del departamento de la bodega elegida, excluidos los marcados **Es bodega** | Empleados de departamentos con al menos un empleado **Es bodega** en esa empresa (por ejemplo, Sistemas o RRHH), excluidos los empleados-bodega |
| **Al generar PDF** | `employee_id` se actualiza al empleado-bodega, `equipment_assign_to = employee`, se registra quién devuelve y quién recibe | Se conserva `equipment_assign_to = department`, `department_id` y `employee_id` tal como estaban; registra quién devuelve y quién recibe |
| **Acta PDF** | Firma del empleado anterior, no de Bodega Sistema | Firma del empleado seleccionado que devuelve, aunque el equipo no tenga un `employee_id` |
| **Historial** | Tipo **Devolución de empleado a bodega**, empleado anterior, bodega, receptor, usuario, fecha | Tipo **Devolución de departamento sin cambio de asignación**, departamento de origen, empleado que devuelve, departamento del receptor, receptor, usuario y fecha |

El campo **Equipo entregado a** toma siempre empleados reales (`hr.employee`) y valida el departamento, la empresa y **Es bodega** tanto en el formulario como al guardar. No crea nuevos empleados.

## Historial de movimiento

La pestaña **Historial de movimiento** permanece después de **Mantenimiento** y muestra una tabla histórica de todos los movimientos. En modo Departamento la columna Bodega queda vacía intencionadamente; el departamento del receptor aparece en su propia columna; no se introduce ninguna bodega ficticia. Las relaciones y los nombres guardados en el momento de cada movimiento permiten conocer quién entregó, quién recibió, la empresa, fecha y usuario registrador. No se borran ni modifican los registros anteriores.

La operación de devolución departamental **no cambia la propiedad/asignación del equipo**: solo genera el acta y añade trazabilidad. Si más adelante se hace otra devolución, se genera otra fila en el historial.

## Actualización desde 18.0.1.12.0

1. Respaldar la base de datos y los addons.
2. Reemplazar **solo** la carpeta `maintenance_report_return_assignment` con el contenido del ZIP, sin desinstalar el módulo.
3. Reiniciar Odoo y actualizar el módulo (desde Aplicaciones o `-u maintenance_report_return_assignment`).
4. Verificar: entrega individual, entrega por departamento, devolución individual a bodega, devolución departamental sin mover el equipo, devolución de varios equipos del mismo origen, firmas PDF e historial.

Migraciones 18.0.1.13.0: el campo opcional de bodega en el historial permite movimientos sin bodega; los movimientos anteriores se clasifican sin alterarse. Se conservan los antiguos campos de último movimiento por compatibilidad, aunque no estén visibles como bloque independiente.

**Pruebas:** validaciones locales de Python, XML, herencia de plantillas y flujos simulados. No existe un servidor Odoo 18 en este entorno; antes de producción hay que probar el módulo en una base de pruebas.

## Corrección 18.0.1.14.0 — actualización de Odoo 18

Se eliminó el campo XML `active` de `ir.actions.server` en `data/maintenance_equipment_bodega_server_action.xml`, porque Odoo 18 no lo admite. La acción antigua continúa sin aparecer en el menú **Acción** al dejar `binding_model_id=False`. No se modifican las devoluciones, las entregas, las validaciones ni el historial de movimientos.

## Versión 18.0.1.15.0 — Firmas de entrega y filtro de receptores

- **Entrega individual:** permanece idéntica a la plantilla original.
- **Entrega por departamento:** después del texto de compromiso aparece el bloque original de firmas en dos secciones horizontales: **ENTREGUE CONFORME** a la izquierda y **RECIBI CONFORME** a la derecha. Los miembros activos del departamento se muestran uno debajo de otro, con nombre y cédula a la izquierda y línea individual de firma a la derecha. Se usa tabla HTML compatible con wkhtmltopdf.
- **Devolución por empleado:** Bodega de devolución es obligatoria; solo puede recibir un empleado no-bodega del departamento de esa bodega; el equipo pasa a la bodega y se registra el historial.
- **Devolución por departamento:** nuevo campo opcional **Departamento receptor (opcional)**. Sin seleccionar un departamento, **Equipo entregado a** ofrece empleados no-bodega de todos los departamentos de la empresa con al menos un empleado marcado **Es bodega**. Al elegir un departamento, la selección se limita a este. El servidor valida la relación aunque se omita el filtro de la interfaz. El equipo continúa asignado al departamento, y se guarda el movimiento en el historial.
- No se vuelven a activar las acciones antiguas de asignación a bodega. Se conserva la corrección de `ir.actions.server` en Odoo 18.
