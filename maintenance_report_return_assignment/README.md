# Maintenance Report — Actas departamentales y devolución a bodega (Odoo 18)

**Módulo:** `maintenance_report_return_assignment`  
**Versión:** `18.0.1.12.0`  
**Dependencias:** `hr_maintenance`, `maintenance_report`, `maintenance_report_unifor`.

## Novedades 18.0.1.12.0

### Acta de entrega

- Si en la ficha de un equipo **Usado por = Departamento**, el PDF **Acta de Entrega** identifica al departamento e imprime, debajo de **RECIBÍ CONFORME**, un listado de líneas de firma para **todos los empleados activos de ese departamento**, de la empresa del equipo. Cada empleado aparece con su nombre y cédula si tiene el dato registrado.
- Si **Usado por = Empleado**, el acta conserva su presentación y las firmas individuales anteriores.
- Para evitar un PDF que atribuya firmas al departamento equivocado, un acta departamental conjunta solo admite equipos del **mismo departamento**. Una entrega uniforme conserva su flujo original.

### Acta de devolución

- La asignación a bodega se realiza **dentro de Generar Acta de Devolución**, no mediante botones separados.
- El wizard ahora incluye, después de **Encargado de entrega/recepción de equipos**:
  1. **Departamento actual** (informativo si la asignación era por departamento).
  2. **Empleado actual**: si el equipo estaba asignado al departamento, elegir un empleado de ese departamento como persona que devuelve; si estaba a nombre de un empleado, se muestra automáticamente ese mismo empleado y no se permite sustituirlo.
  3. **Bodega de devolución**: solo empleados de `hr.employee` con el check **Es bodega**.
  4. **Equipo entregado a (empleado)**: solo empleados del mismo departamento de la bodega, excluyendo empleados con **Es bodega** y validando la empresa.
- **Generar PDF** valida primero toda la selección, actualiza `maintenance.equipment.employee_id` con el **empleado de bodega**, registra la entrega y genera el PDF con **el empleado que hizo la devolución**, no la bodega como origen.
- Se reutilizan las validaciones existentes y el registro de historial por equipo, incluyendo nombre del antiguo empleado, **departamento de origen** cuando aplique, bodega, receptor físico, usuario de Odoo y fecha.
- Para operaciones con varios equipos, deben pertenecer a **un mismo empleado** o a **un mismo departamento**. No se mezcla personal distinto en un solo acta; el usuario deberá generar actas separadas para evitar documentos con firmas incorrectas.
- La selección por departamento no modifica la condición **Es bodega** de ningún empleado. Tampoco crea empleados.

### Cambios en la interfaz

- Se elimina de la ficha del equipo el botón inteligente **Asignar a bodega**.
- Se oculta la antigua acción masiva **Asignar a bodega** del encabezado de la lista y del menú **Acción**; la devolución desde la vista lista sigue disponible con **Generar Acta de Devolución**.
- La pestaña **Historial de movimiento**, después de **Mantenimiento**, muestra la tabla de **Historial de movimientos a bodega**, ahora con una columna **Departamento de origen**.
- No se borra el historial de asignaciones de versiones previas ni el checkbox **Es bodega**.
- El acta de entrega de uniformes sigue como antes.

## Ejemplos

**Equipo asignado al Departamento Sistemas:** Acta de Entrega imprime las firmas de Juan, María, etc. Al realizar devolución, elegir Juan como **Empleado actual**, Bodega Sistema como bodega y María como empleado que recibe físicamente en bodega. El equipo queda con `employee_id = Bodega Sistema`. El acta registra a Juan como quien devuelve. El historial indica Departamento Sistemas, Juan, Bodega Sistema, María, usuario registrador y fecha.

**Equipo de Pepito Pérez:** el wizard muestra Pepito como **Empleado actual** de solo lectura. Se elige la bodega y su receptor y se genera PDF. El equipo queda a nombre de la bodega y el PDF muestra a Pepito como quien devolvió.

## Instalación / actualización

1. Hacer copia de seguridad de base de datos y archivos.
2. Reemplazar **solo** la carpeta del addon `maintenance_report_return_assignment`, sin desinstalarlo.
3. Reiniciar Odoo y actualizar el módulo (`-u maintenance_report_return_assignment` o **Aplicaciones > Actualizar**).
4. Comprobar en un entorno de pruebas: entrega de un equipo departamental, devolución individual, devolución departamental, devolución múltiple de un departamento, filtro del receptor, historial y PDF resultante.

**Nota:** el historial de movimientos anteriores se conserva. Las acciones antiguas de asignación a bodega se desactivan para que las nuevas devoluciones queden documentadas al generar su acta. El modelo auxiliar y la lógica común permanecen por compatibilidad interna.

## Validaciones locales

Comprobadas sintaxis Python, XML, dominios, referencias de herencia de PDF contra los módulos recibidos, archivo ZIP y escenarios de flujo mediante simulaciones. **No hay un servidor Odoo 18 ejecutándose en este entorno**, por lo que se requiere una prueba de instalación y generación real del PDF antes de producción.
