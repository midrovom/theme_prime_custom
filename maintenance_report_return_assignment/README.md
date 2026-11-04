# Maintenance Report - Bodega de devolución (Odoo 18)

**Versión:** 18.0.1.2.0

Extensión independiente de `maintenance_report` y `maintenance_report_unifor`, sin modificar sus archivos originales.

## Objetivo

Al generar el **Acta de Devolución de Equipos**, el campo **Bodega de devolución** permite elegir un contacto marcado **Es bodega**, y el campo real `maintenance.equipment.employee_id` se **reasigna al empleado de esa bodega**.

Por ejemplo: equipo asignado a `Pepito Pérez` → contacto de bodega `Bodega Sistema` → al pulsar **Generar PDF**, `employee_id` pasa a `Bodega Sistema` (registro `hr.employee`). El PDF mantiene a `Pepito Pérez` como la persona que devolvió el equipo.

## Configuración

1. En **Empleados**, debe existir el empleado `Bodega Sistema` en la misma empresa que los equipos.
2. En **Contactos**, crear o abrir el contacto `Bodega Sistema`, activar **Es bodega**.
3. Opcional (recomendado): seleccionar `Bodega Sistema` en **Empleado asociado a bodega** dentro del contacto. Si no se selecciona, la extensión encuentra automáticamente un empleado cuyo `work_contact_id` sea ese contacto, o uno con nombre exactamente igual en la misma empresa, siempre que sea único.
4. Generar el Acta de Devolución desde el módulo habitual y seleccionar el contacto de **Bodega de devolución**.

## Cambios en el equipo

- `employee_id` = empleado vinculado al contacto de bodega (NO se vacía).
- `bodega_devolucion_id` = contacto de bodega seleccionado, a efectos de consulta.
- `empleado_devolucion_anterior_id` = empleado anterior, conservado para el acta de devolución.
- `entregado_por_id` = encargado seleccionado en el wizard, como en el módulo base.
- `partner_id` (proveedor) permanece **sin cambios**, evitando modificaciones de la codificación de equipos.

Las actas de **entrega de equipos** y **uniformes** no cambian.

## Validaciones

- El contacto debe tener **Es bodega** activado.
- No se mezclan empleados anteriores ni empresas en una misma acta.
- El empleado de destino debe existir, estar activo y pertenecer a la empresa del equipo.
- Ante nombres duplicados, se exige elegir **Empleado asociado a bodega** para evitar asignaciones equivocadas.
- No se crean empleados automáticamente.

## Instalación / actualización

Descomprimir la carpeta `maintenance_report_return_assignment` en la ruta de addons. Actualizar lista de aplicaciones e instalar o actualizar el **mismo módulo** si ya se instaló la versión 18.0.1.1.0.

Dependencias: `contacts`, `hr_maintenance`, `maintenance_report`, `maintenance_report_unifor`.

## Alcance histórico

`empleado_devolucion_anterior_id` y `bodega_devolucion_id` reflejan la **última devolución** de cada equipo; no se construye una bitácora independiente de devoluciones. Las actas ya archivadas no se modifican.
