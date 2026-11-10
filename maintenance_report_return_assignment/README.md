# Maintenance Report — Entrega y devolución de equipos con historial (Odoo 18)

**Módulo:** `maintenance_report_return_assignment`  
**Versión:** `18.0.1.20.0`  
**Dependencias:** `hr_maintenance`, `maintenance_report`, `maintenance_report_unifor`.

## Acta de entrega: dos comportamientos independientes

- **Usado por = Empleado:** se mantiene el reporte y el flujo original de entrega, con la firma del empleado al que está asignado el equipo.
- **Usado por = Departamento:** el PDF muestra al departamento responsable y una línea de firma **RECIBÍ CONFORME** para cada empleado asociado directamente al departamento, incluidos los registros archivados. No asigna los equipos a empleados específicos.
- Si se seleccionan varios equipos departamentales para una misma acta, todos deben pertenecer al mismo departamento. La entrega de uniformes no se altera.

## Acta de devolución: flujos diferentes

| Función | Equipos usados por Empleado | Equipos usados por Departamento |
|---|---|---|
| **Empleado actual** | Autocompletado, solo lectura | Seleccionable entre empleados del departamento del equipo |
| **Bodega de devolución** | Obligatoria, solo empleados con **Es bodega** | **Oculta**, no se exige ni se transfiere a bodega |
| **Equipo entregado a (empleado)** | Empleados del departamento de la bodega elegida, excluidos los marcados **Es bodega** | Empleados del **Departamento receptor** seleccionado (por ejemplo, Sistemas o RRHH), excluidos los empleados-bodega |
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

## Versión 18.0.1.16.0 — Firmas de entrega y filtro de receptores

- **Entrega individual:** permanece idéntica a la plantilla original.
- **Entrega por departamento:** después del texto de compromiso aparece el bloque original de firmas en dos secciones horizontales: **ENTREGUE CONFORME** a la izquierda y **RECIBI CONFORME** a la derecha. Todos los empleados vinculados directamente al departamento se muestran uno debajo de otro, con nombre y cédula a la izquierda y línea individual de firma a la derecha. Se usa tabla HTML compatible con wkhtmltopdf.
- **Devolución por empleado:** Bodega de devolución es obligatoria; solo puede recibir un empleado no-bodega del departamento de esa bodega; el equipo pasa a la bodega y se registra el historial.
- **Devolución por departamento (modificada en 18.0.1.16.0):** **Departamento receptor** es obligatorio y ofrece los departamentos de la empresa (incluidos departamentos compartidos). **Equipo entregado a** solo ofrece empleados del departamento seleccionado, excluidos los marcados Es bodega. No es necesario que el departamento receptor tenga una bodega marcada. Se conserva la asignación de origen del equipo y se guarda quién entregó y quién revisó en el historial.
- No se vuelven a activar las acciones antiguas de asignación a bodega. Se conserva la corrección de `ir.actions.server` en Odoo 18.

## Versión 18.0.1.16.0 — Departamento receptor y todos los firmantes

- **Entrega de equipos por departamento:** la lista RECIBÍ CONFORME se basa exclusivamente en la relación `hr.employee.department_id` con el departamento del equipo. Se incluyen empleados archivados y se elimina el filtro por empresa de su ficha para que no falte ningún empleado vinculado; no se agregan miembros de otros departamentos. Se mantiene la entrega individual original.
- **Devolución de equipos por departamento:** `Departamento receptor` ya no es opcional; muestra los departamentos pertenecientes a la empresa del equipo y los compartidos (`company_id` vacío), sin exigir que tengan personal marcado `Es bodega`. `Equipo entregado a` muestra únicamente los empleados de ese departamento, excluyendo los marcados `Es bodega`. Se verifica en el servidor, independientemente de los dominios del formulario.
- Al confirmar la devolución por departamento se registra en historial: persona que entregó, departamento de origen, departamento receptor, empleado receptor, usuario y fecha; el equipo **no cambia** de departamento ni de empleado. El PDF también muestra el departamento y receptor de esa devolución.
- **Devolución por empleado:** sin cambios; sigue requiriendo Bodega de devolución y empleado receptor del departamento de dicha bodega y actualiza `employee_id`.
- Si ya había datos, actualice **el mismo módulo** sin desinstalar para preservar el historial. Verifique en una copia de la base de Odoo antes de producción.


## Versión 18.0.1.17.0 — Selector directo y listado completo de firmas

- **Devolución por departamento:** el dominio de **Equipo entregado a (empleado)** se basa directamente en el `Departamento receptor` seleccionado (sin dependencias de listas Many2many computadas en el wizard). Al cambiar el departamento se borra el receptor anterior y se listan los empleados activos vinculados al nuevo departamento; se excluyen los empleados con **Es bodega**. El botón permanece deshabilitado hasta escoger departamento; las validaciones al guardar siguen verificando que el receptor pertenece al departamento receptor y registrando el movimiento.
- **Devolución por empleado:** el mismo campo muestra empleados del departamento de la bodega seleccionada. El equipo se reasigna a esa bodega y conserva su historial previo.
- **Entrega por departamento:** los firmantes se obtienen de `hr.employee.department_id` del departamento del equipo **y de sus subdepartamentos**, sin filtrar por empresa del empleado y con empleados archivados para soportar reimpresiones históricas. Se sustituyó el bloque flotante por una tabla paginable: izquierda ENTREGUÉ CONFORME; a la derecha un nombre y cédula por fila con su espacio individual para firmar. No se altera la firma original en entrega por empleado.
- No se cambian modelos de historial, datos existentes ni mecanismos de devolución individual/departamental. No es necesario reinstalar; actualizar el módulo conserva los movimientos.

> Los empleados que no tengan asignado el departamento (ni uno de sus subdepartamentos) en su ficha de **Empleados** no pueden identificarse automáticamente como miembros del mismo. Si siguen faltando firmantes, revisar `department_id` en esas fichas.


## Versión 18.0.1.18.0 — Departamentos receptores configurables

- Se añadió **Habilitar como departamento receptor** (`hr.department.permite_recepcion_equipos`), desmarcada por defecto. Solo los departamentos marcados y de la empresa del equipo (o compartidos) aparecen en `Departamento receptor` para las **devoluciones de equipos asignados a departamento**. Configurar desde **Empleados → Departamentos**; marcar Sistemas y RRHH o los departamentos que corresponda en cada entorno. No hay listas por nombre ni por ID.
- **Equipo entregado a (empleado)** sigue mostrando los empleados del departamento receptor seleccionado y excluye los que tengan **Es bodega**, tanto en la interfaz como al generar el acta. Se conserva la validación de empresa y departamento. Para **equipos asignados a empleado**, el filtro sigue basado en el departamento de la bodega seleccionada.
- Se retiró la ayuda visible bajo el selector en el wizard de devolución departamental. La sección extra del PDF que decía **Departamento responsable / Departamento receptor / Recibido-revisado por** ya no aparece; los datos continúan guardándose en el historial, junto con el empleado que entregó, el usuario registrador y la fecha.
- **Los equipos asignados a departamento NO cambian `department_id`, `employee_id` ni `equipment_assign_to`.** El PDF mantiene la identificación de quien devuelve y el reporte de entrega conserva las firmas configuradas en 18.0.1.17.0.
- Tras actualizar el módulo, marcar explícitamente los departamentos receptores deseados; por defecto ninguno está habilitado.


## Versión 18.0.1.19.0 — Distribución de las firmas de entrega por departamento

- Se ajusta **solo el formato** del bloque de firmas de entrega **por departamento**: más margen interno para ENTREGUE CONFORME y una mejor separación horizontal entre el nombre del empleado receptor y su línea de firma.
- El espacio de firma comienza más cerca de cada receptor, con margen derecho para que no quede pegado al borde. Se conserva una fila de firma por empleado y la continuación entre páginas.
- **Entrega por empleado, devoluciones, filtros e historial:** sin cambios de lógica ni de datos.


## Versión 18.0.1.20.0 — Historial de actas de entrega

- Al pulsar **Generar PDF** en un acta **Entrega** se crea una entrada de historial **por cada equipo** incluido.
- **Entrega a empleado:** guarda fecha, empleado destinatario, encargado que entregó, usuario Odoo y fotografía de los nombres al momento del acta. Mantiene la lógica y las firmas del PDF original.
- **Entrega a departamento:** guarda el departamento destinatario, encargado que entregó, fecha y usuario Odoo. También conserva una lista textual histórica de los empleados firmantes que aparecieron en el acta, para que permanezca disponible aunque después cambien los integrantes del departamento.
- La pestaña **Historial de movimiento** muestra ahora las entregas y devoluciones. En cada fila aparece el tipo de movimiento, el destinatario de la entrega, su responsable, la fecha y el usuario registrador. El detalle contiene la lista histórica de firmantes departamentales.
- No se alteran `employee_id`, `department_id` ni `equipment_assign_to` al registrar una entrega: se documenta la asignación ya existente.
- Volver a pulsar Generar PDF en el **mismo wizard** no duplica los registros. Generar otra acta nueva sí registra otro movimiento, pues representa una nueva operación de entrega.
- **No se importan ni inventan actas históricas anteriores** a esta versión; se registran las que se generen después de actualizar el módulo.
- Se conservan sin cambios la lógica de las devoluciones, filtros de bodega/departamentos, historial anterior y diseños PDF.
