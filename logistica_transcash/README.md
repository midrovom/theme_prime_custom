# Logística Transcash V4 — Odoo 18 · PWA offline, roles y video reanudable

**Addon:** `logistica_transcash` · **Versión:** `18.0.4.0.0` · **Estado:** candidato a pruebas (MVP), **NO certificado ni ejecutado en una instancia Odoo 18**. Se verificaron sintaxis Python/JS, XML, estructura del manifiesto y permisos declarativos; faltan pruebas de instalación, rendimiento, compatibilidad de Odoo y navegadores físicos.

## Resumen de arquitectura

La versión 4 conserva el portal móvil de la V3 y añade un flujo segregado de crédito y cobranzas, permisos por modelo y validaciones al ejecutar operaciones, y transferencia en bloques **1 MiB** para que fotos/videos se reanuden tras una interrupción de red. El móvil prepara guías previamente consultadas en IndexedDB; en las rutas `/transcash/guias` y `/transcash/offline` no se cachean páginas de clientes en Cache Storage. El servidor valida la sesión de Odoo, la guía, la etapa y el autor antes de finalizar las cargas.

### Tabla de roles y acciones

| Rol | Lectura | Únicas acciones autorizadas |
|---|---|---|
| Chofer (usuario Odoo portal) | Solo guías asignadas | Foto/video carga, novedades, descarga, llegada, reportes de rotura y respuesta a objeciones |
| Cliente / destinatario (usuario Odoo portal) | Guías de su organización: productos, evidencias, comentarios, roturas e historial operativo | Evidencia de recepción, aprobación/objeción de llegada, confirmación de entrega física y roturas en etapa de recepción |
| Bodega (`group_logistica_bodega`) | Guías de compañías permitidas | Iniciar carga, aceptar/objetar evidencia de carga, autorizar salida |
| Vendedor (`group_transcash_vendedor`) | Guías y evidencias de compañías permitidas | Reportar roturas con producto/cantidad/foto o video desde el portal móvil; no puede aprobarlas |
| Administrador de ventas (`group_transcash_ventas_admin`) | Guías, roturas y solicitudes NC | Aprobar/rechazar roturas y **preparar/enviar propuesta** de NC |
| Aprobador NC (`group_transcash_nc_aprobador`) | Expediente y propuestas | Aprobar/devolver propuesta con justificación; **no puede ser la persona que propuso** |
| Crédito y cobranzas (`group_transcash_cobranzas`) | Guías, evidencias, roturas y propuestas | Enviar solicitud autorizada al ERP, registrar número y **adjuntar/validar comprobante PDF/JPG/PNG** emitido externamente |
| Contabilidad (`group_transcash_contabilidad`) | Guías, evidencias y trayectoria (sin edición operativa) | Configurar valor/cuenta por asistente, autorizar liquidación, crear factura proveedor en borrador, comprobar pago registrado |
| Administrador de logística (`group_logistica_manager`) | Expediente operativo | Coordinar el embarque, incidencias y aprobación global de la guía; no revisa roturas ni emite notas de crédito por su rol operativo |

**Importante:** los permisos **se asignan en Ajustes → Usuarios**, de manera individual. Dar a un usuario grupos de distintas áreas amplía su conjunto de permisos; evite combinaciones innecesarias. La validación impide que la misma persona proponga y apruebe su propia NC incluso si tiene ambos perfiles. El superusuario técnico de Odoo no debe compartirse con personal operativo.

**Importante sobre cliente:** el perfil de destinatario se determina por contacto/empresa vinculados al usuario portal, no por un grupo interno de empleado. Esto impide que un cliente consulte guías de empresas ajenas. Los perfiles internos de consulta acceden solo a compañías habilitadas. Los eventos internos de NC, cuentas y pagos se excluyen del historial visible para destinatarios.

### Flujo de daños y nota de crédito

1. Chofer, vendedor o cliente registra **producto, cantidad y evidencias**; el registro no puede superar el detalle despachado sumando reportes no rechazados.
2. Administración de Ventas **aprueba o rechaza cada rotura**. Para rechazar debe escribir motivo.
3. El administrador operativo valida la **guía completa** después de aceptación del destinatario y revisión de evidencias.
4. Administración de Ventas prepara la solicitud consolidada y pulsa **Enviar propuesta a aprobación**.
5. Aprobador NC acepta o devuelve justificadamente. No puede aprobar su propia propuesta.
6. Crédito y Cobranzas, tras aprobación, envía la solicitud al ERP externo desde Odoo; el ERP emite el comprobante fiscal. También puede recibir confirmación mediante callback autenticado. En Odoo se registra número real y se adjunta **el comprobante oficial**; Crédito y Cobranzas pulsa **Confirmar comprobante emitido**.
7. Contabilidad liquida solo cuando la guía está aprobada, no quedan incidencias abiertas y la NC requerida aparece emitida **y con comprobante validado**. La tarifa de transporte es independiente del valor de la NC.

La **nota de crédito fiscal no se genera en este addon**: permanece en el ERP emisor de las facturas de venta. El addon prepara el expediente con la cantidad rota por SKU, unidad y archivos. No se emiten comprobantes fiscales falsos.

### Resumen de estados de NC

`borrador → propuesta → aprobada → enviada → emitida`.

Alternativas: `propuesta → rechazada_aprobacion → propuesta` (devolución al vendedor administrador) y `enviada → rechazada → aprobada` (rechazo ERP, reintento por Cobranzas). Se permite confirmación por callback ERP con Bearer; el comprobante documental deberá adjuntarse por Crédito y Cobranzas antes de liquidar.

## Subida offline y reanudable

- PWA instalable con **HTTPS**: Android Chrome → Instalar aplicación; iPhone Safari → Añadir a pantalla de inicio.
- Abrir previamente online las guías que serán trabajadas sin conexión; la PWA conserva instantáneas de sus productos y tipos de reporte autorizados.
- Fotos/videos/roturas se guardan **primero en IndexedDB** con UUID idempotente; el usuario ve **pendiente local**, **enviando bloques** o **requiere revisión**.
- Al recuperar señal, si la sesión está vigente, el navegador calcula **SHA-256**, pide al servidor los índices de bloques existentes y envía únicamente los faltantes. Los bloques son de 1 MiB. La finalización comprueba número de partes, tamaño, SHA-256 y firma MIME, y se registra una sola operación por UUID.
- Cuando el servidor confirma el registro de Odoo, se elimina el pendiente del dispositivo. Si pierde la respuesta final, el UUID permite recuperar el acuse evitando duplicar la evidencia o rotura.
- Se intenta sincronización en segundo plano en navegadores compatibles, con alternativa cuando se reabre la webapp, retorna la señal o se pulsa **Sincronizar**. En **iPhone con PWA cerrada no se garantiza una subida en segundo plano**.
- Límites previstos: **6 archivos por reporte; 12 MB/foto; 75 MB/video; 110 MB/reporte**. Archivo fragmentado de 1 MiB y **250 MB por usuario en sesiones temporales simultáneas**. Una tarea diaria purga bloques abandonados durante más de 7 días: el móvil aún conserva el archivo si no se ha confirmado y podrá reiniciar la subida desde el inicio.
- No se almacena contraseña, token ERP ni CSRF en IndexedDB; no se cachea HTML autenticado. El medio pendiente queda sin cifrado de aplicación: use **PIN/biometría del teléfono**, evite dispositivos compartidos y considere MDM para operación empresarial. Desinstalar la PWA, limpiar datos del navegador o liberar espacio puede borrar evidencias sin enviar.
- **Límite técnico actual**: los bloques son persistidos en Odoo y se reconstruyen en la finalización; ello demanda memoria y tiempo en el servidor para videos grandes. Para volúmenes elevados, conviene migrar el ensamblado a almacenamiento de objetos con cargas multipart directas/streaming.

### Endpoints PWA (solo sesión autenticada de Odoo)

- `GET /transcash/sync/session` — sesión actual y CSRF vigente.
- `GET /transcash/sync/chunk/status` — `{ok, received:[0,1,...]}` o `complete:true` si la operación entera ya está registrada.
- `POST /transcash/sync/chunk/part` — multipart con `client_uuid`, `guide_id`, `kind`, `file_index`, `file_count`, `file_size`, `file_sha256`, `file_name`, `file_mime`, `total_chunks`, `chunk_index`, `chunk` binario y `csrf_token`.
- `POST /transcash/sync/upload` — finalización `{chunked:1, file_count, client_uuid, guide_id, kind, captured_at, ...campos}`. Comprueba todas las partes, autor, etapa, producto, cantidad y formatos; crea una operación idempotente.

El API ERP original de guías (`POST /api/transcash/v1/guias`) y el API de nota de crédito (`POST /api/transcash/v1/notas-credito/estado` y descarga autenticada de evidencias) continúan vigentes. Consulte el manual V3 para el JSON de ingreso de guías y la configuración de tokens de integración.

## Instalación/actualización de V3 a V4

1. **Respaldar base de datos, filestore y carpeta del addon V3.** Probar actualización en una copia **staging** de Odoo 18, no directamente en producción.
2. Requiere Odoo 18 con addons personalizados (Odoo.sh o servidor propio). Copiar carpeta `logistica_transcash` al `custom_addons` y reiniciar el servidor.
3. Actualizar apps, ejecutar **Actualizar** sobre `Transcash - Seguimiento de Guías`. Los cambios crean modelos/estados nuevos; comprobar migración de solicitudes NC previas porque V4 introduce `aprobada`, `propuesta`, `documento_validado_por_id` y controles nuevos.
4. Crear usuarios individuales, asignar solo los grupos funcionales necesarios. Para el chofer usar `res.users` de tipo portal; vincular `chofer_usuario_id` en guía. Para cliente vincular `res.partner` destinatario. Para Contabilidad asignar además **los derechos contables estándar de Odoo sobre facturas proveedor**; el grupo Transcash por sí solo no confiere facultad de contabilizar/pagar.
5. Configurar URLs HTTPS y tokens del ERP; validar permisos de compañía, límites del proxy, espacio de filestore, copias de seguridad y rotación de tokens.
6. En móvil, recargar la aplicación con Internet para instalar el **service worker V4**, luego consultar cada guía para preparar las líneas de producto. Conservar la bandeja local anterior antes de borrar cachés. Las operaciones pendientes de V3 mantienen su UUID y archivos, ahora pasan a bloques V4.
7. Probar estrictamente primero: usuario cliente, chofer, vendedor, administrador ventas, aprobador NC, cobranzas y contabilidad. Ejecutar casos de acceso denegado **también por RPC**, no solo ocultación de botones.

## Casos mínimos de aceptación

1. **Destinatario:** ve sus guías en todas las etapas, historial y archivos; no puede iniciar carga, cambiar estado, aceptar evidencias de otro proceso, ni modificar roturas ajenas. No ve el expediente de otro cliente.
2. **Vendedor:** visualiza las guías de sus compañías; registra rotura por SKU y fotos/videos desde teléfono; no aprueba daños ni altera entregas.
3. **Ventas:** aprueba/rechaza roturas y propone NC, pero no puede enviarla al ERP ni marcarla emitida.
4. **Aprobador:** aprueba/devuelve propuesta con motivo; mismo usuario que la propuso, con ambos roles, **no** puede autoaprobar.
5. **Cobranzas:** solamente envía NC ya aprobada, adjunta PDF/JPG/PNG de hasta 12 MB con número ERP y valida archivo. No edita el transporte.
6. **Contabilidad:** consulta guía sin poder editar estado/evidencias/roturas; usa asistente de tarifa/cuenta y autoriza liquidación solo si no hay pendientes; factura proveedor exige permisos estándar Odoo.
7. **Offline:** activar modo avión con 3 fotos y 1 video grande, registrar rotura, cerrar/reabrir PWA; verificar que sobreviven los archivos y se presentan como **pendientes locales**.
8. **Reanudación:** cortar red tras varios bloques de un video (por ejemplo 37/75); retornar conexión y validar que se consultan bloques existentes y NO se reenvían los confirmados. Reintentar finalización con mismo UUID: se registra una sola evidencia/rotura.
9. **Conflictos:** cambiar destinatario, autorización, estado o cantidad de SKU mientras el dispositivo está offline; el servidor debe rechazar operaciones que ya no sean válidas, sin descartar los archivos pendientes.
10. **Otras:** volver a iniciar sesión, cambiar de usuario, Safari iOS, Chrome Android, batería baja, cuota llena, error 413, bloqueo CSRF y recuperación de usuario sobre un dispositivo compartido.

### Restricciones conocidas

- Es un módulo **MVP para piloto**, no ha sido validado con Odoo 18 en ejecución; deben revisarse vistas, secuencia de contabilidad, rendimiento, estados existentes y seguridad con pruebas end-to-end.
- PWA instalable no equivale a una app compilada de App Store/Google Play. No existe garantía de subida con app cerrada, ni de persistencia absoluta del medio en almacenamiento del teléfono.
- El sistema usa el ERP externo para la emisión fiscal de NC; la API real de ese ERP todavía requiere mapear campos, errores, autenticación y documento original.
- La cuenta y los permisos contables estándar deben ser configurados por la administración de Odoo, respetando compañías y políticas de pago.
