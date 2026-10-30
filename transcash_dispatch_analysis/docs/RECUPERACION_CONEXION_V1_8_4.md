# Recuperación de una carga interrumpida · versión 1.8.4

El mensaje Connection to dispatch.snapshot/process_import_step couldn't be established or was interrupted corresponde al procesamiento de una carga ya recibida. Indica que el navegador no obtuvo una respuesta completa; por sí solo no demuestra pérdida de datos, un nuevo problema de fechas ni la causa exacta de la desconexión.

## Qué cambia

- Con el cron **Despachos: procesar importaciones por bloques** activo, el navegador hace una solicitud corta para despertar el trabajo y después consulta el avance cada 1,5 s. La preparación y escritura de facturas las hace el trabajador de cron. El navegador no llama a process_import_step en ese modo.
- Con el cron desactivado, se conserva la carga interactiva, limitada a 100 facturas por operación y un presupuesto de 500 líneas. Una factura con más de 500 líneas se procesa completa en una sola operación, para conservar la unidad de la factura. No se promete una duración fija si un documento individual es excepcionalmente grande.
- Los bloques preparados de versiones anteriores pueden contener 500 facturas. El nuevo cursor processed_count guarda cuántas ya fueron confirmadas en cada uno. Se procesa su siguiente porción sin volver a crear el prefijo. El cursor, los registros y el contador se guardan en la misma transacción de Odoo, sin commits manuales.
- Si se pierde una lectura, se reintenta hasta tres veces antes de dejar un mensaje para consultar después. Si se pierde una respuesta de escritura, primero se lee el avance persistido; no se supone que la operación falló ni se comienza otra importación. Las interrupciones consecutivas también tienen un límite.
- Los errores de validación del servidor se muestran y no se reintentan como si fueran problemas de red. El botón Reintentar de una carga con error usa su origen guardado, no vuelve a descargar la API.
- La actualización por compañía + TipoFactura + NumeroFactura y la publicación del corte al terminar no cambian. El cron de consulta getdatosdespachos sigue con su programación de dos horas. El adaptador de fechas 1.8.2 no se modifica.

## Instalar y retomar

1. Reemplazar la carpeta transcash_dispatch_analysis por la de este ZIP.
2. Reiniciar Odoo y actualizar el módulo desde Aplicaciones. Verificar la versión **18.0.1.8.4**. Este paso crea el campo del cursor y carga los nuevos métodos; copiar archivos o reiniciar solamente no actualiza el esquema.
3. Recargar el navegador con **Ctrl+F5**. El texto exacto «El archivo queda guardado en Odoo. Esta pantalla procesa los registros y muestra el avance» pertenece a la interfaz anterior. En 1.8.3 y posteriores una carga ERP se identifica por su origen guardado y muestra Sincronización desde el ERP.
4. Abrir **Importaciones e histórico**, seleccionar la misma carga pendiente y pulsar **Procesar / ver progreso**. Si tiene un error de datos, revisar ese error y usar Reintentar sobre la misma carga después de corregirlo. No volver a importar el Excel.
5. Comprobar en Acciones planificadas que **Despachos: procesar importaciones por bloques** esté activo para usar el modo de segundo plano. El conector manual no requiere activar el cron de consulta de dos horas.

## Si el servidor vuelve a interrumpirse

El archivo examples/diagnostico_importacion_odoo_shell.py es de solo lectura y está pensado para ejecutarse dentro de un Odoo shell del administrador con la configuración/base correctas. Muestra la carpeta del módulo que realmente usa el servidor, versiones, cron y últimas cargas pendientes. No contiene credenciales ni modifica la base. Permite detectar que se reemplazó una copia diferente en addons_path o que sigue pendiente la actualización.

Para conocer la causa del corte se necesitan los logs de Odoo y del proxy del instante exacto: excepciones, reinicio del proceso, límite de tiempo, memoria o respuesta 502/504. Esta entrega no cambia límites del servidor ni configura Nginx, porque no se tiene acceso a esa infraestructura.

Validación local: 222 pruebas Python, 19 verificaciones de controlador y 14 verificaciones de navegador real con servicios controlados. Dos pruebas nativas adicionales incluidas para ejecutar en la base de pruebas Odoo; no se afirma instalación o validación contra el servidor remoto.
