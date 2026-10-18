# Transcash V5.17 — Roles, permisos y flujos PWA/Odoo 18

## Objetivo

La WebApp abre la pantalla que corresponde al rol del usuario, sin mezclar planificación, aceptación de embarque, recepción, negociación o pagos. La dirección principal es **`https://TU_DOMINIO/transcash`**. Los usuarios internos trabajan en Odoo y pueden usar la PWA de Logística cuando estén habilitados; los roles externos permanecen como usuarios Portal.

## Matriz de responsabilidades

| Perfil | Tipo de cuenta | Puede realizar | No puede realizar | Entrada recomendada |
|---|---|---|---|---|
| Jefe de Logística — `Administrador de logística` | Interno | Crear hojas de ruta, agregar guías, armar viajes, grabar videos por ruta, liberar carga, administrar destinos/tarifario, negociar y aprobar fletes | Registrar pago bancario (sin rol Contabilidad) | `/transcash/operacion` y menús de Odoo |
| Operador Logística — `Operador Logística: planificar rutas y registrar carga` | Interno | Crear rutas, seleccionar guías, confirmar, armar embarques, subir/validar videos, liberar al chofer, consultar viajes | Cambiar precios maestros, aprobar fletes, pagos, aceptación del chofer | `/transcash/operacion` |
| Responsable de Bodega | Interno | Consultar guías y embarques; acciones de bodega de flujos históricos si corresponden | Planificar nuevas rutas sin perfil Operador; aprobar fletes o pagar | `/transcash/guias` |
| Chofer | Portal + grupo Chofer, activado en directorio | Ver videos de sus rutas, aceptar/rechazar carga, iniciar viaje, llegar a destino, evidencia y firma de entrega | Crear rutas o embarques, subir video de carga, asignar guías, negociar fletes | `/transcash/embarques` |
| Cliente / Destinatario | Portal + grupo Cliente | Consultar solo sus guías, recibir y aceptar, registrar comentarios, novedades, roturas y evidencia | Ver viajes de otros clientes, crear rutas, aprobar pagos | `/transcash/guias` |
| Empresa transportista | Portal + grupo Transportista | Consultar solo viajes propios y valores autorizados, crear liquidación agrupada, adjuntar factura externa, consultar pagos | Cambiar valores, rutas, guías o pagos | `/transcash/proveedor` |
| Vendedor | Interno + Vendedor | Consultar guías e incidencias, gestionar roturas según su autorización | Planificar rutas, aprobar fletes, registrar pagos | `/transcash/guias` y Odoo |
| Administración de Ventas | Interno | Revisar roturas y elaborar propuestas de crédito | Liquidar o pagar fletes | Odoo |
| Aprobador de NC | Interno | Revisar/aprobar/rechazar notas de crédito | Cambiar viajes o pagos | Odoo |
| Crédito y Cobranzas | Interno | Registrar/adjuntar NC emitida externamente | Crear rutas o registrar pagos de transporte | Odoo |
| Contabilidad | Interno | Revisar liquidaciones, consultar guías y evidencias; aprobar/observar factura y registrar pagos con comprobantes | Modificar guías, evidencias o el precio negociado | Odoo → Liquidaciones y pagos |
| Analítica | Interno con permiso independiente | Solo dashboard logístico y exportación autorizada | Crear rutas, modificar pagos o guías por tener únicamente ese permiso | Odoo → Transcash · Indicadores |

Los permisos **Jefe Logística: autorizar flete con incidencias pendientes** y **Analítica: consultar dashboard logístico** siguen siendo adicionales, NO habilitados automáticamente a todos.

## Flujo de Logística disponible en PWA

1. **Centro de operaciones → Crear hoja de ruta.** Elegir empresa transportista, chofer activado, destino del maestro, placa y tipo de vehículo.
2. **Agregar guías.** Marcar guías pendientes del destino. Si la asignación ERP difiere, marcar la autorización explícita; el servidor conserva auditoría al confirmar. Guardar la selección y confirmar la hoja.
3. **Armar embarque.** Marcar una o varias hojas del mismo chofer/placa/transporte; elegir destino de cobro y aplicar **UNA tarifa por el embarque completo**.
4. **Documentar video.** Desde cada hoja confirmada e incluida en un embarque en preparación, cargar un MP4/MOV/WebM (máximo 75 MB). Se valida en el servidor.
5. **Liberar al chofer.** Cuando todas las rutas tienen video validado, entrar al embarque y liberar. El chofer acepta por su cuenta Portal; el operador NO puede simular su aceptación.
6. **Entrega.** Chofer registra recepción, foto/video, nombre y firma. Cliente acepta o registra novedades después; el pago sigue el circuito separado.

## Alta y comprobación de usuarios

1. En Odoo, abra Ajustes → Usuarios y compañías → Usuarios. Verifique el **tipo de usuario** (Interno para Logística, Portal para chofer/cliente/proveedor).
2. Asigne **solo el grupo Transcash apropiado**. Para chofer, use además la ficha `Choferes y acceso móvil` y active su cuenta Portal.
3. Con cada usuario, abra `https://TU_DOMINIO/transcash`. Compruebe que aparezcan solo las entradas autorizadas.
4. Haga las pruebas con tres cuentas separadas (Operador, Chofer y Cliente). No confíe en el menú si un usuario tiene varios grupos solapados.

## Pruebas de regresión recomendadas

- Operador: ve «Crear hoja de ruta», «Armar embarque» y abre «Embarques» sin 404 ni error de acceso.
- Jefe de Logística: ve lo mismo y puede administrar tarifas y aprobar flete desde Odoo.
- Chofer: no ve botones de creación de rutas/embarques y no puede acceder por URL directa a `/transcash/operacion`.
- Cliente/proveedor: no pueden ingresar a `/transcash/operacion` ni consultar guías de otra compañía/cliente.
- Contabilidad: consulta documentos, guías y evidencias sin poder cambiarles el estado; pago solo desde métodos autorizados.
- Solo Analítica: puede usar indicadores sin recibir acceso a guías operativas.
- Se validan guías, múltiples rutas, tarifa única por embarque, videos, aceptación del chofer y posterior entrega.

## Actualización del módulo

Respaldar PostgreSQL, filestore y carpeta `logistica_transcash`. Reemplazar la V5.16 por la V5.17, reiniciar Odoo y **actualizar el módulo, sin desinstalarlo**. Recargar la WebApp instalada para renovar el manifiesto y caché del navegador; no borrar evidencias offline pendientes sin sincronizarlas antes.

**Alcance y límite de pruebas:** se revisaron código, XML, rutas y permisos de forma estática. Las pruebas de integración con usuarios y permisos efectivos requieren una base Odoo 18 en ejecución; hasta realizarlas no debe considerarse garantizado el comportamiento de producción.

## Compatibilidad con PWA instalada antes de V5.17

Algunos accesos instalados en el teléfono conservan la URL de inicio antigua `/transcash/guias`. Para usuarios internos con rol Operador o Jefe de Logística, la V5.17 redirige esa entrada antigua al nuevo **Centro de operaciones**, sin borrar los datos offline. Para consultar deliberadamente la lista de guías desde Logística se utiliza `/transcash/guias?vista=consulta`. Los choferes, clientes y transportistas mantienen sus recorridos propios.

Los enlaces de creación, selección de guías, ensamblaje de embarque, video y liberación tienen control de acceso **en cada ruta HTTP y en los métodos de Odoo**. Los menús por sí solos no se consideran mecanismo de autorización.
