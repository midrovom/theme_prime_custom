> Documento histórico. La versión 1.8.14 sustituye el UPDATE de etiquetas por presentación dinámica sin conversión histórica. Consulte ACTUALIZACION_LIGERA_V1_8_14.md.

# Actualización segura 18.0.1.8.13

El log de la versión 1.8.12 contiene una factura externa 16039 con banderas de clientes, fechas, ciudades y vendedores inconsistentes. No se puede asumir que el número externo por sí solo sea único por compañía. Esta versión vuelve a la base 1.8.10 y usa el número externo como etiqueta y búsqueda, sin utilizarlo para fusionar registros. La identidad de los indicadores sigue siendo empresa + TipoFactura + NumeroFactura. Se conserva `external_number` en la base; las importaciones nuevas generan `FAC/<externo>` y los bloques preparados también se adaptan.

## Antes de actualizar

1. Detener todos los procesos Odoo que usan la base; comprobar que no queda una actualización en ejecución. Copia de seguridad de BD y filestore.
2. Consultar `SELECT name,state,latest_version FROM ir_module_module WHERE name='transcash_dispatch_analysis';`.
3. Si la actualización anterior falló y la versión persistida es 18.0.1.8.10 (o anterior compatible), retirar la carpeta antigua COMPLETA, no superponer los archivos. En particular no deben quedar scripts bajo `migrations/18.0.1.8.11/`. Extraer esta carpeta en addons.
4. Si 18.0.1.8.11 o 18.0.1.8.12 figura instalada, NO actualizar directamente: la conversión pudo haber fusionado facturas y eliminado detalles. Restaurar el respaldo anterior o preparar una recuperación específica a partir de los originales. La migración se detiene en ese caso, sin modificar facturas.
5. Ejecutar con el usuario del servicio, entorno virtual y configuración habituales: `./odoo-bin -c /ruta/odoo.conf -d themeConedera -u transcash_dispatch_analysis --stop-after-init --no-http --workers=0 --max-cron-threads=0`. Iniciar el servicio solo si finaliza correctamente.

La actualización desde 1.8.10 verifica las claves existentes y ejecuta un único UPDATE SQL de `name` para las etiquetas distintas. No borra, fusiona ni recrea facturas, líneas, cortes, relaciones, plazos ni favoritos. No llama al ORM para recalcular indicadores. Puede requerir tiempo y espacio de WAL según el volumen y carga del servidor. No hay commits parciales. Las instalaciones anteriores a 1.6 conservan su migración histórica original, independiente de este cambio.

El error `cursor already closed` no prueba por sí solo la causa del cierre: revisar las líneas anteriores del log, el gestor del servicio y los registros del sistema si se repite. No cancelar una actualización activa sin comprobar su estado. La validación local no sustituye una prueba con la base de datos y Odoo 18 del cliente.
