# Maintenance Report - Bodega de devolución (Odoo 18)

**Versión:** 18.0.1.3.0 (actualización de `maintenance_report_return_assignment`).

## Funcionamiento

Solo cuando el wizard se abre desde **Generar Acta de Devolución**, debajo de
**Encargado de entrega/recepción de equipos** aparece **Bodega de devolución**.
Este campo utiliza **hr.employee**, igual que el campo **Empleado** de los
equipos (`maintenance.equipment.employee_id`).

Ejemplo:
- Antes: Equipo → **Empleado = Pepito Pérez**.
- En el wizard: **Bodega de devolución = Bodega Sistema** (empleado existente).
- Al pulsar **Generar PDF**: Equipo → **Empleado = Bodega Sistema**.
- El PDF identifica a **Pepito Pérez** como persona que devuelve y a
  **Bodega Sistema** como destino; mantiene al encargado de recepción.

No se necesitan contactos ni casillas **Es bodega**, ni se crean empleados
nuevos. Las actas de entrega y uniformes permanecen sin cambios.

## Notas

- El empleado elegido debe existir en **Empleados** y ser visible al usuario.
- Si se devuelven varios equipos, deben pertenecer a un mismo empleado anterior
  (el acta original tiene un único nombre y firma de devolución).
- `empleado_devolucion_anterior_id` conserva el empleado previo para imprimir
  el acta después de actualizar `employee_id`; no aparece como opción en el wizard.
- El módulo no modifica el proveedor (`partner_id`) ni los datos de contacto.
- El registro del empleado anterior refleja la **última devolución**; este
  módulo no crea un historial independiente de actas.

## Instalación y actualización

Descomprimir `maintenance_report_return_assignment` en los addons de Odoo 18,
reiniciar Odoo, actualizar la lista de aplicaciones y **Actualizar** el mismo
módulo si la versión anterior ya está instalada. El script de migración retira
las vistas antiguas de Contactos y Equipos que mostraban los campos obsoletos.

Dependencias: `hr_maintenance`, `maintenance_report`, `maintenance_report_unifor`.
