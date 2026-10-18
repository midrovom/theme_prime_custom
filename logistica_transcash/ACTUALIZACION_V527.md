# TRANSCASH V5.27 — Aprobar flete desde PWA sin esperar al cliente

**Actualización de** `18.0.5.26.0` **a** `18.0.5.27.0` · Odoo 18 · Módulo `logistica_transcash`.

## 1. Incidencia original y diagnóstico

La V5.26 tenía dos problemas:

1. El botón **«Aprobar flete y publicar al proveedor»** estaba escondido en **Finanzas PWA** (`/transcash/finanzas/embarques/<id>`), pero no aparecía en el **detalle operativo del embarque** (`/transcash/operacion/embarques/<id>`) desde el cual Logística trabaja normalmente. Tampoco había acceso inmediato para aprobar desde un enlace histórico a `/transcash/embarques/<id>`.
2. El método `_ensure_finance_ready()` exigía aprobación global del cliente, cierre de incidencias, resolución de roturas y nota de crédito, aunque el chofer hubiera finalizado todas las entregas. En ese caso el POST de aprobación se rechazaba incluso si el botón se veía.

## 2. Regla operativa implementada

**Un embarque puede publicarse al proveedor para facturar cuando:**

- Su **estado de viaje es Entregado** (`transcash.embarque.state == 'entregado'`).
- Todas las **guías han sido cerradas por el chofer** (`fecha_cierre_chofer`), o se encuentran en estados históricos finales (`entregada`, `lista_pago`, `facturada`, `pagada`).
- **Todas las hojas de ruta** asociadas están completas y tienen guías. Los embarques históricos sin hoja de ruta conservan compatibilidad.
- El importe **único por embarque** es positivo y existe empresa transportista.
- El viaje no está aprobado, no figura en otra liquidación y no tiene liquidaciones históricas bloqueadas.
- El actor es un **usuario interno con el grupo Jefe / Responsable de Logística** y tiene autorización para la compañía.

**Ya NO se exige** la aceptación posterior del destinatario, la aprobación global de las guías, el cierre de reportes de daño, el tratamiento de notas de crédito ni la confirmación de incidencias para aprobar el **flete del transportista**. Esas gestiones continúan abiertas para las áreas internas correspondientes. No se ocultan ni se borran.

> El cierre del chofer es un control operativo indispensable. La independencia de los reclamos del cliente **no** significa que puedan pagarse viajes sin terminar de entregar.

## 3. Qué cambia en la PWA

### Jefe de Logística

- Desde `/transcash/operacion` aparece la opción clara **«05 · Aprobar fletes»**, con contador de embarques entregados aún sin aprobar.
- Desde el **detalle de un embarque terminado** aparece **«Aprobar flete y enviar al proveedor»**, con el precio negociado, acceso a revisar o registrar el precio y alerta informativa si hay novedades internas.
- El botón también se presenta al entrar por enlaces anteriores a `/transcash/embarques/<id>`.
- Desde `/transcash/finanzas` puede consultar viajes listos para aprobar; desde su detalle puede negociar el importe, revisar rutas/guías/evidencias y aprobar.
- Si el monto es cero o la ruta no está completa, el botón se deshabilita y el servidor también bloquea la petición.

### Operador de Logística

- Puede consultar el avance, los documentos y el estado de aprobación, pero **no recibe el botón** de autorizar fletes. La aprobación corresponde al jefe.

### Transportista (Portal)

- El embarque aprobado se muestra en la lista de **viajes aprobados pendientes de liquidación** de `/transcash/proveedor`, sin requerir aceptación del cliente.
- Puede agrupar los viajes aprobados, calcular el total de fletes y presentar su factura según el proceso V5.24. No puede alterar importes ni estados de aprobación.

### Chofer y Cliente

- **No ven precios, aprobaciones financieras ni botones de liquidación**.
- El cliente sigue gestionando conformidad, reclamos y evidencias **solo sobre sus propias guías**.

### Contabilidad

- No aprueba el precio del flete. Consulta viajes aprobados y liquidaciones; controla factura, pagos y confirmación del proveedor conforme a la V5.24.

## 4. Chatter y concurrencia

- La **negociación del precio** mantiene la bitácora anterior/nuevo/motivo introducida en V5.24.
- Al aprobar se registra **importe, nombre del responsable y publicación al proveedor** en el chatter del embarque.
- Si existen guías con novedades abiertas, se anota que se tramitan por separado.
- La aprobación usa bloqueo de filas de embarque y guías y comprueba el estado nuevamente antes de escribir, para evitar doble aprobación concurrente.
- Los embarques ya aprobados y liquidaciones existentes **no se modifican automáticamente**.
- Se conserva el mecanismo excepcional histórico para registros anteriores, aunque ya no se necesita su botón para aprobar un flete con incidencias.

## 5. Instalación segura

1. Hacer **respaldo completo de PostgreSQL**, filestore y carpeta del módulo actual.
2. Instalar primero en una copia de pruebas de la base real.
3. Reemplazar la carpeta `logistica_transcash` por la carpeta contenida en el ZIP.
4. Reiniciar Odoo, actualizar la lista de aplicaciones y ejecutar **Actualizar** sobre `logistica_transcash`, sin desinstalarlo.
5. Limpiar solo la caché de recursos del navegador/PWA cuando no haya adjuntos pendientes de sincronizar. No borrar datos offline del chofer.
6. Confirmar que el usuario que ejecuta la acción es **interno** y tiene `group_logistica_manager`; un **Operador Logística** no puede aprobar.
7. Verificar el nuevo menú y la ficha del mismo viaje en el móvil y el backoffice.

## 6. Pruebas de aceptación imprescindibles en Odoo 18

| Prueba | Datos iniciales | Resultado esperado |
|---|---|---|
| A | Embarque entregado, todas las guías cerradas por chofer; cliente sin responder | Jefe aprueba; proveedor ve viaje pendiente de liquidar |
| B | Embarque entregado, incidencia o rotura abierta | Jefe aprueba flete; incidencia se conserva y sigue abierta |
| C | Un guía de la ruta sin cerrar por chofer | Rechazo en servidor, sin aprobación ni publicación |
| D | Hoja de ruta vacía/incompleta en viaje histórico inconsistente | Rechazo con causa concreta |
| E | Flete igual a 0 | No permite aprobar; exige registrar valor negociado |
| F | Usuario operador, Contabilidad, cliente o chofer intenta aprobar | Acceso denegado; no cambia el estado |
| G | Jefe aprueba dos veces o dos pestañas concurrentes | Solo una aprobación; segunda operación rechazada |
| H | Proveedor agrupa viajes aprobados y sube factura | Total correcto y documento aparece en Contabilidad |
| I | Contabilidad registra pago, proveedor confirma | Estados de Contabilidad/proveedor independientes y concordantes |
| J | Cliente reporta novedad después de la aprobación | El reporte permanece privado y no revierte aprobación financiera |

## 7. Alcance real de las verificaciones

- Pruebas de sintaxis Python, XML y JavaScript; integridad del ZIP; comprobación de rutas y permisos declarados.
- Siete pruebas aisladas ejecutadas de la **función real** de elegibilidad económica.
- Pruebas `TransactionCase` añadidas en `tests/test_aprobacion_independiente_v527.py`. **No se ejecutaron** en Odoo 18 en este entorno.
- No se puede garantizar el funcionamiento en el VPS del usuario sin ejecutar las pruebas anteriores con su base y usuarios.

**La operación y la conformidad del cliente son procesos distintos. El transporte se autoriza tras cerrar operativamente todas las rutas y guías; los reclamos internos siguen su tratamiento sin bloquear el cobro legítimo del proveedor.**
