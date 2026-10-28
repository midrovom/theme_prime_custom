# Transcash Guías API 18.0.2.35.0 — Planificación editable

Complemento de Logística Transcash v5.32. No cambia el módulo base.

## En la PWA

- Hoja de ruta en borrador o planificada, sin vínculo con embarque: **Eliminar hoja de ruta** con confirmación. Libera las guías confirmadas; no borra las guías ERP.
- Embarque en preparación o liberado (`embarcado`) y **sin aceptación del chofer**: **Eliminar viaje no aceptado** con confirmación; desliga hojas de ruta y guías, conservando evidencias de carga y los datos de las guías.
- Detalle de embarque en preparación: selector de **rutas ya confirmadas compatibles** y botón **Agregar al viaje actual**. Permanece el mismo viaje, sin crear un flete adicional.
- Si aún no hay ruta compatible, **Crear hoja de ruta para este viaje** precarga transportista, chofer, tipo de vehículo y placa; luego el operador selecciona las guías, confirma y vuelve al viaje para incorporarla.

## Bloqueos del servidor (también por ORM)

- Hoja de ruta: no se elimina si está vinculada a un embarque, contiene guías de un viaje, evidencia de carga, entrega o aceptación.
- Viaje: no se elimina si hay aceptación efectiva o histórica del chofer, salida o entrega, liquidaciones, aprobación, incidencias/objeciones del chofer o guías que ya salieron.
- Las operaciones requieren los permisos actuales de operador de rutas o jefe de Logística y compañía autorizada.
- Las peticiones de modificación desde PWA son POST con CSRF y confirmación; protecciones de bloqueo transaccional evitan cambios concurrentes.
- Se reutiliza `transcash.armar.embarque.wizard.action_confirm()` para agregar rutas, manteniendo las verificaciones de permisos, mismo vehículo/chofer/transportista y máximo de 100 guías por viaje. Las modalidades contratado/cliente se conservan.

## Instalación

1. Respaldar PostgreSQL y carpeta `transcash_guias_api`.
2. Reemplazar únicamente la carpeta por esta versión y reiniciar Odoo 18.
3. Actualizar `transcash_guias_api` desde Aplicaciones y recargar PWA.
4. Probar con usuario operador: eliminar ruta planificada sin embarque; eliminar embarque en preparación y otro embarcado sin aceptar; vincular ruta nueva al embarque existente.
5. Probar con chofer: aceptar otro embarque y confirmar que se bloquea su eliminación tanto en PWA como en backend.
6. Probar un viaje con objeción o liquidación; no debe permitir eliminación.

Validaciones locales: Python AST, XML, JS y XPath contra v5.32. No se ejecutó Odoo con base real en este entorno.
