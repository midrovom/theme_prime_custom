# Transcash – Guías ERP (Odoo 18)

## Preparación indispensable

1. Ubica el **nombre técnico del addon** que define `api.administrator` (no el nombre del modelo). En `__manifest__.py`, agrega a `depends` el addon que define `api.administrator` (además de `logistica_transcash`) antes de instalar. Esto garantiza el orden de carga de `_inherit = 'api.administrator'`.
2. El modelo `api.administrator` existente debe tener `name`, `type`, `company_id`, `status`, `call_api()` y `button_run_sync()` tal como el usuario compartió.
3. En la configuración API crea/activa: name = `getguiaslogistica`; type = `get`; status = `A`; company_id = empresa correspondiente; url + end_point = URL que resuelve `inventory_odoo/consulta_odoo/getguiasaut/2`; y credenciales.
4. Asigna grupo `Administrador de integración guías` a un usuario administrador. Ejecuta el botón de sincronización **en esa configuración**. Por código: `env['tc.guide.sync'].sync_from_api(company_id)`.
5. La pantalla `Transcash - Guías ERP` muestra guías importadas, no las inserta en una hoja de ruta operativa previa: ese enlace necesita los nombres técnicos de modelos y relaciones reales de la instalación.

## Contrato

- Se espera un objeto de respuesta `{'success': true, 'data': [ ...]}`; `data` contiene guías agrupadas con `detalle`.
- Los datos no operativos (marca y proveedor producto) se guardan en `tc.guide.line.private`. Sin lectura permitida para operador o jefe. Otros grupos no reciben ACL por este addon.
- Los maestros de transportistas/proveedores **solo** se crean con RUC/identificación fiscal **explícitos y verificados externamente**; no se infieren de códigos variables ni nombres.
- Remitente, destinatario y destino se crean si hay códigos no vacíos. El campo `-NAJ` se trata como código ERP de destinatario, **no** como RUC.
- Se hace upsert por empresa + id_externo y por guía + id_linea. Los artículos no presentes en respuestas posteriores no se borran.
- Cada guía se procesa dentro de un savepoint para aislar errores; la ejecución genera registro de auditoría.

## Limitaciones deliberadas para evitar afectar el desarrollo existente

- Las tablas `tc.*` son nuevas tablas de importación y maestros; no alteran las tablas operativas de ruta y embarque actuales. No se presupone su esquema.
- El addon no expone endpoint nuevo: consume el API existente.
- No modifica el PWA ni crea asignaciones automáticas a embarques.
- Para uso productivo revisa políticas de actualización de cabeceras modificadas y agrega mapeo de roles de portales; el addon no concede permisos a chofer/proveedor de transporte/cliente.
- Revisar equivalencia semántica de `peso_kg`, `cajas`, `pallets` y unidad de medida de cantidad.
- Se validó sintaxis Python y XML de origen; todavía no se realizó instalación/pruebas contra base real Odoo 18.


## Integración directa con Logística Transcash v5.32 (sin tercer addon)

Se integró el anterior puente en `models/api_bridge.py` de **este mismo addon**.
El botón `Sincronizar` de `transcash.guia`, el cron y las acciones `Probar` / `Sincronizar` del asistente ahora consultan `getguiaslogistica` mediante `api.administrator.call_api`.
No leen `logistica_transcash.api_url` y no exigen URL HTTPS adicional en Ajustes.
**La bandeja `tc.guide` sigue separada del modelo operativo `transcash.guia`** para no intervenir rutas, embarques, evidencias y liquidaciones.

**Actualización**: sustituye exclusivamente el directorio `transcash_guias_api` por este y actualiza el addon en Odoo 18. No se instala `transcash_api_bridge`.
Si tienes instalado previamente `transcash_api_bridge`, desinstálalo antes de actualizar este paquete para evitar dos overrides del mismo método.
Mantén los nombres y configuración de la API en API Administrator: `getguiaslogistica`, GET, estado A, empresa correcta, credenciales y endpoint.


## Actualización 18.0.1.4.0 - Kanban y menú integrado

- Guías importadas **y guías operativas**: tarjetas Kanban adaptativas con origen, destino, transportista, chofer, placa,
  fecha prevista, estado de publicación, líneas, peso, pallets y cajas. Los totales informativos
  se calculan desde las líneas recibidas y **no incluyen datos comerciales**.
- Se mantiene el mismo XMLID de acción/vista para que la actualización preserve la navegación.
- El menú independiente `Transcash - Guías ERP` se reubica bajo Logística y se desactiva,
  igual que su acceso duplicado. La vista queda en **Logística Transcash → Operación logística → Guías importadas ERP**.
- Historial de sincronización ERP se mueve a Operación logística y sigue visible solo a administradores de integración.
- No cambia la API, los modelos de guías operativas ni las reglas de publicación v1.3.

Actualizar el addon `transcash_guias_api` y recargar el navegador (Ctrl+F5 para recursos estáticos).

- La acción existente `logistica_transcash.action_transcash_guia` cambia a `kanban,list,form` y gana una vista Kanban para `transcash.guia` desde este addon; no se editan archivos de v5.32.
