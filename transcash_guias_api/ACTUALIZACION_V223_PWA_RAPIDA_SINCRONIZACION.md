# v2.23 — Creación de rutas más rápida y refresco manual de guías (Odoo 18)

## Modificación únicamente en `transcash_guias_api`

- El POST de `/transcash/operacion/rutas/nueva` comprueba por búsqueda puntual el chofer, transportista y destino seleccionados. No reconstruye todas las listas de 500 guías para validar un único registro.
- El GET del formulario agrupa por campos de chofer y transportista con `read_group` de Odoo; ya no materializa centenares de guías solo para reunir opciones.
- El selector que sigue a la creación usa **el código ERP del destino seleccionado** (`ruta.destino_id.codigo`) y `transcash.guia.destino`, de acuerdo con la regla aprobada. Primero reduce la búsqueda en PostgreSQL y después valida chofer y proveedor con los métodos estrictos existentes. Nunca autoriza por coincidencia de nombres.
- La búsqueda por número de guía o documento se aplica directamente a la consulta de datos, inclusive si hay miles de guías de otros destinos. Se presentan lotes acotados para evitar cargar enormes listas en el móvil. Se mantienen las guías ya seleccionadas y el máximo de 100 por selección.
- Los indicadores de las tarjetas se consultan mediante recuentos sin reconstruir tablas de diagnóstico.
- Los tiempos de creación y de consulta de guías quedan en `odoo.log` como `PWA creación ruta=` y `PWA ruta=... candidatos=`.
- Botón POST **Sincronizar guías ERP** en PWA: Hojas de ruta, Nueva hoja de ruta y Detalle de ruta en borrador. Restringido por `_guard()` a personal interno operador de rutas o jefe de Logística, y se valida también en servidor; no hay acceso Portal.
- La llamada utiliza `transcash.guia._transcash_run_api_sync` / `getguiaslogistica` configurada en `api.administrator`. No requiere una segunda URL ni expone credenciales al cliente. Se impiden dos ejecuciones manuales simultáneas por compañía con `pg_try_advisory_xact_lock`.
- Se mantiene el loading anti-doble envío de v2.22; ahora muestra texto específico al sincronizar.

## Nota operativa

La **sincronización real del ERP es una petición separada**, iniciada solo al pulsar el botón. Puede tardar según la API externa y el número de registros. El guardado ordinario de la ruta no hace llamadas al ERP.

En bases muy grandes, evaluar un índice de expresión para el código de destino, tras medir el plan de ejecución y hacer respaldo. No se ejecutan DDL ni migraciones de PostgreSQL automáticamente.

## Validaciones recomendadas (base de pruebas)

1. Crear hoja de ruta nueva con chofer, empresa y destino existentes; revisar que redirija al detalle.
2. Seleccionar y guardar guías compatibles por **destino, chofer y proveedor**; confirmar que continúa el límite de 100 y que no se incluyen guías ocupadas.
3. Buscar una guía antigua por número o documento y verificar que aparezca si está disponible.
4. Como operador autorizado, pulsar Sincronizar guías ERP; comprobar nuevas guías en el listado e historial. Repetir como usuario Portal: debe rechazarse.
5. Probar dos envíos concurrentes, para la misma empresa: solo uno debe ejecutar la sincronización.
6. Consultar `odoo.log` y medir tiempos antes/después; el tiempo depende del tamaño de su PostgreSQL y no puede certificarse sin ejecutar en ese entorno.

No se modifican rutas confirmadas, liquidaciones, evidencias, tarifarios ni reglas de permisos financieros.
