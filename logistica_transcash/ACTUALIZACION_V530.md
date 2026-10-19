# TRANSCASH V5.30 — Backoffice intuitivo, vistas kanban y Contabilidad (Odoo 18)

**Actualiza sobre:** V5.29 · **Versión:** `18.0.5.30.0` · **Aplicación:** `logistica_transcash`.

## 1. Problema y enfoque

Antes de V5.30, las hojas de ruta, los embarques y las liquidaciones se consultaban principalmente en listas. En el caso de Contabilidad, los viajes pendientes, las facturas y los pagos estaban separados sin una entrada de trabajo claramente identificable. Existía también un menú legado «Liquidaciones antiguas (por guía)», que no representa el procedimiento vigente: **el proveedor cobra un único flete por embarque**.

V5.30 mantiene la PWA actual para choferes, clientes, Logística y proveedor. **Contabilidad trabaja en el escritorio Odoo, sin requerir una segunda PWA.** Sus vistas son nativas de Odoo 18, con selección alternativa de **kanban, lista y formulario**.

## 2. Menús reorganizados

Desde **Logística Transcash**:

| Apartado | Opciones principales | Personal |
|---|---|---|
| **Operación logística** | Hojas de ruta, armar embarque, embarques/viajes, guías para planificación, choferes, acceso clientes, tarifario y aprobación de fletes | Según grupos existentes de Logística, Bodega y consulta |
| **Contabilidad · Transporte** | Bandeja contable, viajes por liquidar, facturas recibidas, liquidaciones y pagos, transferencias y conciliación, acceso proveedores | Contabilidad y, en los apartados autorizados previamente, jefe de Logística |

El menú antiguo **Liquidaciones por guía** se desactiva visualmente. **No se elimina ningún registro histórico**.

## 3. Tarjetas kanban y su uso

### Embarques

Cada tarjeta muestra: embarque, estado, alerta de objeción de carga, transportista, chofer, placa, rutas completadas/total, guías entregadas/total, salida real o prevista, entrega real o prevista. Haciendo clic se abre el embarque, sus hojas de ruta, sus guías, el chatter y la galería de carga/descarga/firmas. **No hay importes económicos en esta tarjeta operativa**.

### Hojas de ruta

Cada tarjeta muestra destino, embarque, transportista/placa, estado operativo y avance de entregas. Haciendo clic se abre la hoja con sus guías y evidencias agrupadas. El listado clásico sigue estando disponible para búsquedas densas.

### Liquidaciones — bandeja de Contabilidad

Cada tarjeta muestra proveedor, estado documental, número de factura (o ausencia), **fletes aprobados, factura, pagos, saldo** y estado de confirmación del proveedor. Al abrirla:

1. **Ver viajes incluidos**: lista los embarques de la liquidación (cada embarque abre sus rutas, guías y evidencias).
2. **Ver factura**: visualiza el PDF o imagen adjunta en el navegador mediante la ruta privada existente.
3. **Aprobar factura** o **Observar factura**: únicamente si está en revisión y el usuario tiene autorización contable.
4. **Registrar pago**: solo después de aprobar la factura, con comprobante bancario y controles existentes.
5. **Ver transferencias**: muestra el historial; abriendo una transferencia, se puede **Ver comprobante** sin descarga obligatoria y verificar el estado de recepción del proveedor.

La bandeja tiene filtros «Facturas por revisar», «Observadas», «En pago», «Pagadas» y «En gestión». Se puede agrupar por estado, proveedor o compañía.

### Transferencias y conciliación

La bandeja permite buscar transferencias y filtrar por «Proveedor por confirmar», «Diferencias», «Confirmadas» o «Anuladas». Se conserva una separación estricta: **Contabilidad registra el pago; el proveedor puede confirmar su recepción o reportar diferencias desde su Portal; la diferencia no revierte unilateralmente el estado contable**.

## 4. Responsabilidades y permisos

- **Operador de Logística**: planifica rutas, elige guías, arma embarques, adjunta evidencia, libera viajes. No aprueba fletes ni registra pagos.
- **Jefe de Logística**: negocia y aprueba un flete por embarque cerrado, registra acuerdos en chatter y lo publica para el proveedor.
- **Proveedor transportista (Portal)**: incluye viajes autorizados en liquidaciones, presenta factura y confirma recepción de transferencias. No edita importes aprobados ni pagos.
- **Contabilidad (usuario interno Odoo)**: revisa viajes y evidencias, examina facturas, observa o aprueba y registra pagos, consulta discrepancias y gestiona los accesos del proveedor.
- **Chofer (Portal)**: continúa usando la PWA, con navegación Embarque → Ruta → Guía; no ve importes ni pantallas de Contabilidad.
- **Cliente (Portal)**: sigue viendo únicamente sus guías y recepciones, sin información financiera ni embarques de otros clientes.

Los nuevos botones de navegación validan **rol interno y compañía autorizada en el servidor** antes de devolver acciones de Odoo. Las reglas de registro previas siguen vigentes.

## 5. Diseño adaptable y evidencias

- Tarjetas con lectura rápida en escritorio, tableta y teléfono.
- Formularios de Contabilidad más claros, accesos directos y pestañas existentes intactas.
- Visores anteriores de carga, descarga y firma: se conservan en embarque y hoja de ruta.
- La PWA no recibe alteraciones de su lógica offline ni del visor de fotografías.
- Se conserva el chatter histórico de negociaciones, aprobaciones y pagos.

## 6. Instalación sin perder datos

1. **Respalde PostgreSQL, filestore y el código actual V5.29**. Ensaye primero en una copia de la base.
2. Extraiga el ZIP V5.30. Sustituya la carpeta **`logistica_transcash`**, no el directorio completo de addons.
3. Reinicie Odoo y actualice únicamente el módulo `logistica_transcash`, desde Aplicaciones o mediante el mecanismo de actualización de su servidor (`-u logistica_transcash`). **No desinstale**.
4. Actualice recursos del navegador (recarga forzada) y compruebe que aparecen las dos secciones nuevas y el selector de vistas kanban/lista.
5. No borre el almacenamiento de la PWA si existen evidencias pendientes de sincronización.

## 7. Pruebas funcionales que deben realizarse en el VPS

| Nº | Usuario | Caso | Resultado esperado |
|---|---|---|---|
| 1 | Operador Logística | Abrir Embarques en kanban y abrir una ruta | Tarjeta → Embarque → Hojas de ruta → Guías; evidencias accesibles |
| 2 | Jefe Logística | Abrir viaje entregado, negociar precio y aprobar | Chatter registra negociación y aprobación; visible al proveedor |
| 3 | Contabilidad | Abrir «Bandeja contable» | Tarjetas con proveedor, estado, flete, factura, pagado y saldo |
| 4 | Contabilidad | Abrir una liquidación con varios viajes | «Ver viajes incluidos» ofrece embarques, no guías sueltas |
| 5 | Contabilidad | Abrir factura y comprobante desde Odoo | PDF/imagen visualizable sin descarga obligatoria |
| 6 | Contabilidad | Aprobar factura y registrar pago parcial y total | Saldo disminuye; estado `pagada` solo cuando pagos válidos cubren factura |
| 7 | Proveedor Portal | Confirmar pago o reportar diferencia | La recepción cambia; el pago contable no se altera |
| 8 | Contabilidad | Ir a Transferencias → Diferencias | Solo transferencias objetadas; apertura del documento y su comprobante |
| 9 | Chofer Portal | Entrar a PWA | No se muestran valores ni menús contables; sigue embarque → ruta → guía |
| 10 | Cliente Portal | Abrir recepción | Solo sus guías; no puede abrir liquidaciones ni otras entregas |
| 11 | Multiempresa | Contable de A abre URL documental de B | Se deniega por grupos/reglas de compañía |
| 12 | Móvil | Abrir kanban, cambiar a lista y luego formulario | Legibilidad y navegación sin desbordamientos laterales graves |

## 8. Validación previa realizada y limitaciones

Se revisaron sintácticamente **66 Python, 31 XML y 10 JavaScript**, junto con referencias del manifiesto y plantillas kanban; también se probó la distribución estática en Chromium a 320, 390, 768 y 1280 píxeles. Se incluyen pruebas de Odoo `tests/test_backoffice_ux_v530.py`, **pendientes de ejecución con ORM real**.

**No se puede garantizar funcionamiento en su VPS sin instalar esta versión en un clon con los registros reales, ejecutar tests Odoo y completar la matriz anterior.** La pantalla móvil se probó como disposición de diseño, no como una sesión de Odoo conectada.

El módulo sigue siendo documental; no integra contabilidad nativa (`account.move`), ni hace transferencias bancarias.
