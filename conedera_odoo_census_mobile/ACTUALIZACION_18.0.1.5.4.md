# Catastro - App de Campo 18.0.1.5.4 (Odoo 18)

## Objetivo

Corregir el aviso erróneo de almacenamiento de la 18.0.1.5.3 y ubicar la cotización dentro de cada ficha de catastro.

## Modificaciones

- Se elimina el timeout de 2,5 s sobre la apertura de IndexedDB. Una apertura lenta o temporalmente bloqueada no invalida los datos almacenados ni impide consultar Odoo.
- Se mantiene la base IndexedDB `conedera-field-app` y la cola `pending`, sin `deleteDatabase`, `clear` de pendientes ni migración de esquema obligatoria. Las cachés opcionales de cotizaciones continúan compatibles con la versión 1.
- La lectura local se ejecuta en segundo plano. En línea, la interfaz consulta el servidor inmediatamente y no muestra una alerta roja causada únicamente por una espera de IndexedDB.
- Si el almacenamiento está realmente inaccesible, las operaciones **conectadas** se envían directamente a `/catastro/app/sync` con UUID idempotente, solo tras validar sesión y compañía con `/catastro/app/ping`. Los errores de servidor se muestran sin afirmar que el registro se guardó.
- Las operaciones **sin conexión** siguen requiriendo que IndexedDB esté disponible: nunca se hace una promesa de guardado offline sin persistencia comprobable.
- Se elimina el acceso genérico «Cotizar ahora» de portada y navegación. Dentro de un catastro finalizado y protegido aparece un botón prominente **Crear cotización**. El cliente queda preseleccionado y no puede reemplazarse por otro en el formulario.
- Se preservan las funciones existentes de catastro, visitas, horarios, cierre, aprobaciones y cotizaciones rápidas. Los campos avanzados de Ventas personalizados siguen requiriendo los módulos correspondientes para integrarse en la PWA.
- Nuevas claves de caché PWA y parámetros de versión de los archivos estáticos; se conserva el alcance `/catastro/` y el acceso normal de Odoo en `/web`.

## Actualizar

1. Respalde la base de datos y **sincronice los pendientes si es posible**.
2. Sustituya únicamente la carpeta técnica `conedera_odoo_census_mobile` y actualice este módulo (no desinstalar).
3. Reinicie Odoo, actualice el módulo y cargue `/catastro/app?version=18.0.1.5.4`.
4. Entre en **Mis catastros**, seleccione un cliente protegido y pulse **Crear cotización**.
5. En **Más → Datos sin conexión**, compruebe si el almacenamiento está conectado antes de intentar operaciones sin cobertura.

Nunca use «Borrar datos del sitio» si hay pendientes locales. No se ha validado la instalación en el servidor real ni en sus módulos personalizados de Ventas; haga primero una prueba en un entorno de Odoo 18.
