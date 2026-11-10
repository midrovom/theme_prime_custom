# Maintenance Report — Asignación individual y masiva de equipos a bodega (Odoo 18)

**Versión:** `18.0.1.7.0`. Actualiza el mismo módulo
`maintenance_report_return_assignment` sin desinstalarlo.

## Novedad en la versión 18.0.1.7.0

- En **Equipos > vista de lista**, marcar las casillas de **uno o varios**
  equipos. Aparece el botón de cabecera **Asignar a bodega** (sin necesidad
  de entrar a cada ficha). También está disponible en **Acción > Asignar a
  bodega** para listas personalizadas.
- Abre un único wizard que muestra la **cantidad de equipos seleccionados**
  y permite elegir **una bodega para todos**.
- Los destinos siguen siendo empleados (`hr.employee`) con **Es bodega**
  habilitado, y se filtran por empresa. No se usan contactos.
- Cada equipo actualizado cambia `maintenance.equipment.employee_id` y
  mantiene su **propio empleado anterior** en
  `empleado_devolucion_anterior_id`; el tipo de asignación pasa a **Empleado**
  (no Departamento), y guarda el usuario y la fecha en
  `bodega_asignado_por_id` y `bodega_asignacion_fecha`.
- Se escribe una nota individual en el historial de cada equipo modificado.
- Los equipos ya asignados a la bodega elegida **no se modifican**; si todos
  estaban asignados, se avisa y no se realiza ningún movimiento.
- Se impide mezclar equipos de distintas empresas en un mismo lote.
- El botón inteligente en el formulario de un único equipo **continúa**.
- El wizard original del acta de devolución permanece **sin cambios**.

## Uso

1. En **Empleados**, marcar **Es bodega** en Bodega Sistema.
2. Abrir **Mantenimiento > Equipos** en vista de lista, seleccionar varios
   equipos mediante sus casillas.
3. Pulsar **Asignar a bodega** (o el menú **Acción > Asignar a bodega**).
4. Seleccionar **Bodega Sistema** y confirmar una sola vez.
5. En cada equipo, verificar **Empleado**, **Empleado anterior**, **Registrado
   por** y **Fecha de asignación a bodega**.

## Actualización

Reemplazar la carpeta existente, reiniciar Odoo y ejecutar la actualización
`-u maintenance_report_return_assignment` o desde Aplicaciones.
Mantener instalados `hr_maintenance`, `maintenance_report` y
`maintenance_report_unifor`. No desinstalar antes de actualizar, para
preservar los campos de auditoría y su información.

**Pruebas:** comprobaciones locales de lógica, XML, Python y empaquetado.
Validar el botón en la vista de lista concreta utilizada en la base de Odoo 18
antes de desplegar en producción.
