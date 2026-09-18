# Validación — Conedera Catastro 18.0.1.8.1

## Resultado

**VALIDACIÓN ESTÁTICA: APROBADA**

Se validó el contenido final del addon antes de empaquetar.

### Sintaxis y estructura

- 36 archivos Python parseados/compilados sin error de sintaxis.
- 18 archivos XML parseados correctamente.
- 112 IDs XML explícitos sin duplicados dentro del módulo.
- Manifiesto válido con versión `18.0.1.8.1`.
- Todas las rutas `data` y `web.assets_backend` del manifiesto existen.
- Todos los JavaScript del addon pasan `node --check`.
- Los botones `type="object"` de las vistas apuntan a métodos Python existentes.
- Las referencias ACL de modelos custom fueron contrastadas con los `_name` del addon.
- No se detectaron campos calculados no almacenados usados en `default_order`.

### Seguridad y flujo auditados

- Búsqueda global normalizada por RUC/cédula, incluso cuando el VAT está en contacto hijo.
- La información sensible de un Catastro ajeno no se devuelve en el autocomplete.
- Selección del autocomplete revalidada en servidor contra los resultados de la búsqueda actual.
- Restricción de `res.partner` aplicada a `commercial_partner_id`, cubriendo contactos hijos.
- Comercial: acceso al Catastro propio.
- Líder de Equipo de Ventas: acceso al equipo que lidera.
- Administrador de Ventas: acceso global.
- Reasignación/archivo/desactivación/control bloqueados a edición directa para usuarios no administradores.
- Horarios de atención reutilizan el bloqueo backend del Catastro.
- Vendedor no puede eliminar un Catastro activo.
- Solicitudes de edición y reasignación mantienen auditoría y actividades.
- Reasignación conserva el mismo `res.partner` e historia asociada.
- Proformas históricas del Catastro reasignado: ampliación únicamente de lectura para responsable actual/líder de equipo.
- Concurrencia del mismo RUC/cédula protegida con advisory lock transaccional de PostgreSQL más constraint de negocio.

### Migración 18.0.1.8.1

- Incluye `pre-10-data-guard.py` y `post-90-data-guard.py`.
- No contiene `DELETE FROM`, `TRUNCATE`, `DROP TABLE` ni `DROP COLUMN`.
- Protege conteos de Catastros, visitas, horarios, tipos, marcas, proformas originadas, solicitudes de edición/reasignación y adjuntos de fotos.
- Si un conteo protegido disminuye, el post-migration lanza error para provocar rollback.
- Duplicados históricos de RUC/cédula se reportan; no se eliminan automáticamente.

### Pruebas de regresión agregadas al suite Odoo

Se añadieron casos para:

- RUC almacenado en contacto hijo y reutilización de la ficha principal.
- Rechazo de un `partner_id` que no pertenece a los resultados de búsqueda.
- Supervisor sin capacidad de reasignar/archivar/desactivar por edición directa.
- Contacto hijo oculto para vendedor ajeno antes de reasignar.
- Conservación del mismo cliente y visitas después de reasignar.
- Lectura por el nuevo responsable de proforma y líneas históricas creadas por el vendedor anterior.

## Limitación de esta validación

Este entorno no tiene instalado el runtime de Odoo 18 ni PostgreSQL de la instancia del usuario, por lo que el suite `TransactionCase` no pudo ejecutarse aquí. Los tests están incluidos para ejecutarse en un servidor Odoo 18; la validación definitiva de ORM/record-rules es el `-u conedera_odoo_census` y las pruebas funcionales sobre una copia de la base real.
