# Maintenance Report — Entregas a bodega con receptor e historial (Odoo 18)

**Versión:** `18.0.1.11.0`  
**Módulo técnico:** `maintenance_report_return_assignment`  
**Actualiza el módulo instalado** (sin desinstalar).

## Cambio de la versión 18.0.1.11.0

- **Equipo entregado a (empleado)** solo muestra empleados del mismo departamento de **Bodega de devolución** que **NO** tengan marcada la casilla **Es bodega**. También excluye explícitamente al empleado seleccionado como bodega.
- Si dentro del departamento hay varios empleados con **Es bodega**, ninguno puede seleccionarse como receptor.
- Se valida igualmente al confirmar, incluso en asignación masiva o a través de llamadas RPC: no es posible registrar como receptor un empleado marcado **Es bodega**.
- El equipo continúa asignado a la bodega seleccionada; los demás campos, el historial, la pestaña y el PDF no cambian.

## Cambio visual de la versión 18.0.1.10.0

- La pestaña anteriormente llamada **Última asignación a bodega** se denomina ahora **Historial de movimiento**.
- Se retiró de la vista la sección **Último movimiento a bodega**. Solo queda visible el apartado **Historial de movimientos a bodega** con la tabla de movimientos.
- Los campos de auditoría del último movimiento se conservan internamente para compatibilidad y para la trazabilidad; no se eliminan registros anteriores.
- El botón de asignación individual y masiva, el filtro «Es bodega», el receptor por departamento y las actas no se modifican.

## Funcionalidad conservada de la versión 18.0.1.9.0

1. En **Mantenimiento > Equipos > Asignar a bodega** (individual o masivo), debajo de **Bodega de devolución** se añadió **Equipo entregado a (empleado)**. El campo selecciona registros de `hr.employee` cuyo `department_id` sea igual al departamento del empleado de bodega seleccionado y que **no** estén marcados como **Es bodega**. Se aplica también el filtro de empresa. El campo se limpia al cambiar la bodega y es obligatorio.
2. La bodega seleccionada debe tener un **departamento** en su ficha de empleado. De lo contrario, se muestra un aviso de configuración y se impide confirmar.
3. El `maintenance.equipment.employee_id` **continúa siendo la bodega** elegida, por ejemplo **Bodega Sistema**. El empleado receptor solo identifica a **quién se entregó físicamente** el equipo dentro de ese departamento.
4. En la ficha del equipo, inmediatamente **después de Mantenimiento**, la pestaña **Historial de movimiento** presenta solo el apartado **Historial de movimientos a bodega**.
5. La tabla del **Historial de movimientos a bodega** con una fila por equipo y operación. Guarda fecha, empleado anterior, bodega, receptor físico y usuario que registró, junto con una copia de los nombres de ese momento para conservar el contexto si luego se renombran.
6. Si un equipo ya está en esa bodega, pero cambia el receptor, se permite registrar un **traspaso interno** como movimiento nuevo, sin alterar el empleado original guardado para el PDF. Si tanto bodega como receptor siguen iguales, se omite el equipo (no se duplica la historia).
7. Se conserva el registro en el chatter del equipo. El historial estructurado tiene permisos de **solo lectura** desde la interfaz y está separado por empresas.

## Ejemplo

- Equipo: Laptop HP
- Empleado anterior: **Pepito Pérez**
- Bodega de devolución: **Bodega Sistema** (`hr.employee`, departamento **Sistemas**, `es_bodega=True`)
- Equipo entregado a: **Juan López** (empleado del departamento **Sistemas**)
- Registrado por: **Administrador de Odoo** (usuario conectado)

Después de confirmar:

- `maintenance.equipment.employee_id` = **Bodega Sistema**.
- Movimiento registrado: **Pepito Pérez → Bodega Sistema**, recibido por **Juan López** y registrado por el usuario conectado.
- La tabla de historial conserva ese movimiento incluso si más adelante se registra otro.
- El PDF de acta no cambia de wizard y conserva la persona original en el documento, como en versiones anteriores.

## Asignación masiva

Desde la lista de Equipos, marque varios registros y use **Asignar a bodega** desde la cabecera o desde **Acción**. Elija una bodega y un receptor del mismo departamento: cada equipo tendrá su **registro propio** con su empleado anterior, bodega, receptor, usuario y fecha.

No se mezclan compañías. La selección y el departamento se validan tanto en el formulario como en el servidor.

## Actualización y registros antiguos

Sustituya los archivos del módulo actual, reinicie Odoo y actualice `maintenance_report_return_assignment` desde Aplicaciones o con `-u maintenance_report_return_assignment`. No lo desinstale.

Se incluye una migración para conservar **una instantánea de la última asignación a bodega** existente en versiones antiguas cuando los datos permiten identificarla, sin inventar el receptor que antes no se guardaba. Movimientos todavía más antiguos solo quedan en el chatter, si están presentes: no se pueden reconstruir fielmente a partir de los tres campos de última asignación.

**Dependencias conservadas:** `hr_maintenance`, `maintenance_report`, `maintenance_report_unifor`.

## Validación

Se verificó sintaxis Python, XML, referencias, contenido del ZIP y flujos de selección de departamento, cambio de receptor, reasignación individual y masiva con simulaciones locales. No se dispone de un servidor Odoo 18 ejecutándose aquí; verifique el flujo real antes de pasar a producción.
