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


## Actualización 18.0.1.5.0 — Kanban de guías para rutas y carga acumulada

- Nuevo menú en **Logística Transcash → Operación logística → Guías para armar rutas**. Filtra únicamente estado Registrada y guías sin hoja de ruta o embarque. La elegibilidad final sigue verificándose dentro del asistente de asignación.
- La vista `transcash.guia` ahora utiliza el mismo formato de tarjeta que las importadas, con 6 métricas: líneas activas, peso, m², unidades, pallets y cajas.
- Nueva vista Kanban de `transcash.hoja.ruta` con destino, transporte, chofer, placa, estado, guías seleccionadas/confirmadas y 6 métricas. Se reemplaza el vínculo de vista de la acción existente de v5.32 sin modificar ese addon.
- En borrador se calcula la carga desde `seleccion_guia_ids`; en estados posteriores desde `guia_ids`. No se duplica el peso.
- El asistente **Agregar / quitar guías** mantiene casillas, búsqueda, bloqueos y autorización de reasignación, pero incluye columnas informativas m², unidades, pallets y cajas.
- El formulario/lista de la hoja de ruta incluye resumen logístico de solo lectura. No toca estados, liquidaciones, proveedores comerciales ni registros PWA.
- Para actualizar: reemplazar solamente `transcash_guias_api`, reiniciar, actualizar addon y Ctrl+F5 en el navegador.

## Actualización 18.0.1.6.0 — Contactos Odoo + acceso a Portal/PWA

Esta versión mantiene la v5.32 operativa y actualiza **solo** `transcash_guias_api`.
Las guías importadas en `tc.guide` se publican en `transcash.guia`; sus terceros se
reconcilian con **`res.partner`** y sus usuarios Portal habilitados con **`res.users`**.

### Reglas de vinculación

- **Transportista**: buscar por RUC explícito (`transportista.ruc`) en `res.partner.vat`.
  Reutilizar contacto existente o crear empresa. Sin RUC NO inventar empresa ni
  tomar el campo `proveedor` variable del detalle como RUC de transportista.
- **Chofer**: buscar por `chofer.identificacion` en `res.partner.vat` y crear
  contacto si falta; enlazar `res.users` solo si ya es un usuario **Portal**, con
  grupo `Chofer Transcash` y con su acceso no revocado. Si es un usuario legacy
  autorizado y carece de registro `transcash.chofer`, crear su ficha SIN otorgar
  permisos ni crear cuentas.
- **Remitente**: buscar `res.partner.vat` cuando `remitente.codigo` tiene forma
  de identificación, o `res.partner.ref` para el código ERP; crear si falta.
- **Destinatario**: buscar por `destinatario.identificacion` / `ruc` (si se
  envía), o `destinatario.codigo` en `res.partner.ref`. `-NAJ` es un **código**,
  NO una cédula. No reconciliar destinatarios por nombre para evitar mostrar
  guías de otro cliente.
- **Proveedores de productos y marcas**: permanecen en `tc.guide.line.private`
  (y modelos privados) con permisos de administrador. No se copian a las líneas
  de guías operativas ni se introducen indiscriminadamente en Contactos.
- **Guías**: `remitente_id`, `destinatario_id`, `proveedor_id` corresponden a
  contactos `res.partner`. `chofer_usuario_id` apunta a un `res.users` Portal
  activo, NO a `tc.driver`. Esto habilita el filtro original de la PWA de v5.32.
- **Viajes y liquidaciones**: se siguen creando en Logística Transcash al
  planificar rutas/embarques. No se crean viajes ni pagos desde el importador.
  El acceso del proveedor se filtra por `proveedor_id.commercial_partner_id`.
- **Seguridad**: ninguna importación crea `res.users`, asigna grupos Portal,
  concede acceso a clientes o transportistas, ni modifica activaciones.
  Conceder Portal usando Contactos y los menús de Accesos Portal existentes.
- **Reimportación segura**: la guía en ruta o embarque no cambia de chofer,
  transporte ni estado. Se pueden completar remitente/destinatario vacíos; para
  completar un proveedor o chofer vacío ya asignado, el vinculo debe coincidir
  exactamente con el que figura en la ruta/embarque.
- **Multiempresa**: se buscan contactos globales o de la compañía correcta;
  códigos duplicados y cédulas ambiguas se dejan pendientes, sin fusionarlos.

### Conciliar guías ya importadas

Tras actualizar el addon y reiniciar Odoo, desde **Logística Transcash →
Operación logística → Conciliar terceros y portales** ejecuta la reconciliación
para la compañía actual. En cada formulario de **Guías importadas ERP** existe
el botón **Conciliar terceros y portales**. Revisa **Vínculos con el portal**,
**Pendientes / observaciones de accesos**, y los campos vinculados a Contactos.
Puedes ejecutar `getguiaslogistica` nuevamente con API Administrator; es
idempotente y hace la conciliación al importar.

### Datos del ERP que pueden impedir acceso automático

Si transportista.ruc está vacío, la guía se importa y publica, pero no se
vincula la empresa de transporte: primero corrige el JSON del ERP. Los ejemplos
previos tienen `transportista.nombre = EZTRANSLOGIST S.A.` pero no RUC confirmado;
la columna original `proveedor` varía por línea y NO identifica consistentemente
al transportista. Si el destinatario llega como `codigo=-NAJ`, verifica que
`res.partner.ref` del contacto/empresa autorizado en Portal contenga ese código;
no se interpreta como RUC. Si el chofer solo tiene contacto y no usuario Portal,
invítalo desde Odoo y habilita el acceso mediante las acciones originales de
Logística. La importación nunca activa perfiles por su cuenta.

### Verificación funcional

1. En Contactos, verifica `vat` y `ref` de transportista, chofer y cliente.
2. Desde `Guías importadas ERP`, comprueba vínculos a `res.partner` y
   `res.users`, y los estados `Vínculos verificados` / `Pendiente de vinculación`.
3. Desde `Guías para armar rutas`, verifica que el contacto proveedor, el
   destinatario y el chofer (si está habilitado) figuren en la guía operativa.
4. Crea una hoja de ruta de prueba y su embarque; accede como chofer Portal
   **preexistente y habilitado** a `/transcash/embarques`.
5. Accede como cliente Portal de ese destinatario a `/transcash/guias` y como
   proveedor Portal a sus viajes y liquidaciones (estas últimas solo cuando
   exista una liquidación).
6. En guías con viajes en curso, verifica que se conservaron estados, chofer,
   empresa transportista, evidencias, firmas y liquidaciones.

**Importante:** no se ha ejecutado el módulo en el servidor del cliente.
La validación disponible es estática (Python, XML y empaquetado); probar primero
con copia de la base Odoo 18.
