# Transcash Guías API v2.26 — Transporte enviado por el cliente

## Alcance
- Sin cambios en el addon `logistica_transcash` v5.32.
- Dos modalidades en `transcash.embarque`:
  - **Contratado** (predeterminada): mantiene aceptación y cierre del chofer, negociación de flete y liquidación.
  - **Enviado por cliente**: carga documentada por Logística; traslado despachado sin aceptación del chofer; cierre por operador/jefe con constancia y trazabilidad; recepción posterior del destinatario.
- La selección de modalidad se hace al **armar embarque** (backend y PWA) o corrigiendo un embarque aún en preparación sin valores ni liquidaciones.
- Los viajes del cliente mantienen `valor_acordado = 0`, `estado_aprobacion = no_aplica` y `estado_financiero = no_aplica`. No se permiten aprobaciones de flete ni inserción de líneas de liquidación.
- No se crea firma, aceptación, salida ni evidencia artificial del chofer. `fecha_cierre_logistica` registra el responsable y momento del cierre por Logística.
- El destinatario puede revisar su guía y confirmar recepción, incluyendo novedades y roturas, después del cierre operativo.
- El Portal cliente muestra un enlace a evidencia de carga. Si una ruta agrupa guías de **destinatarios comerciales distintos**, se bloquea compartir las fotografías generales de esa ruta para evitar exposición de datos entre clientes; se mantienen las evidencias asociadas exclusivamente a la guía.

## Compatibilidad
- Para preservar el esquema y las reglas v5.32, las hojas de ruta siguen requiriendo referencias al usuario de chofer y proveedor de transporte como datos de planificación, **pero ambos quedan exentos de intervenir en el Portal cuando la modalidad es cliente**.
- Los embarques ya existentes permanecen con modalidad `contratado` de forma predeterminada; no se recalculan pagos históricos.
- Los permisos se validan en servidor: modalidad y cierre solo para operadores/jefes internos, factura/liquidación de viajes cliente prohibida, chofer/proveedor sin acceso a esas tareas.

## Prueba de aceptación sugerida en una copia de Odoo
1. Crear ruta y documentar carga; armar embarque en modalidad Cliente.
2. Confirmar que no se cargó tarifa; que estado financiero sea No aplica.
3. Despachar en PWA, registrar constancia de entrega desde Logística. Verificar viaje Entregado y guías En revisión del cliente, sin `fecha_cierre_chofer` ni firma ficticia.
4. Portal destinatario: ver guía y evidencia propia; confirmar recepción o novedad.
5. Portal proveedor: embarque de cliente ausente y no seleccionable para liquidar. Intentar crear línea de liquidación por RPC; debe rechazarse.
6. Portal chofer: viaje del cliente ausente; viaje normal mantiene aceptación y cierre.
7. Jefe de logística y contabilidad: no puede negociar, aprobar ni pagar viaje cliente; un viaje Contratado conserva el flujo anterior.
8. Probar ruta con varios destinatarios: ninguna fotografía general de la ruta debe mostrarse a uno solo de ellos.

Validación realizada fuera del servidor: compilación Python, XML y XPath de v5.32, estructura de ZIP. Se requiere prueba funcional y respaldo antes de instalar en producción.
