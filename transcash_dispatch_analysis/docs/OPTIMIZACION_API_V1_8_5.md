# Importación del ERP más eficiente · 18.0.1.8.5

La versión anterior aplicaba el límite interactivo de 100 facturas también al cron. Además, la consulta ERP normalizaba los mismos nombres de columnas por cada fila y volvía a ordenar todos los registros en una base SQLite temporal durante la preparación.

## Cambios

- **Menos bloques en segundo plano.** El cron empieza con hasta 500 facturas y 2.500 líneas por transacción. Un bloque de 500 preparado por una versión anterior puede terminarse de una vez, o retomarse desde su cursor ya guardado. La carga interactiva conserva 100 facturas/500 líneas.
- **Tamaño según el trabajo observado.** Al terminar cada paso se mide su duración, incluido el vaciado ORM del savepoint. El siguiente tamaño se ajusta entre 50 y 500 facturas, con un objetivo orientativo de tres segundos y un crecimiento máximo de dos veces por paso. El presupuesto de líneas es cinco veces el tamaño elegido. Una factura que por sí sola excede el presupuesto se escribe completa; no se promete un tiempo fijo por documento.
- **Preparación directa para nuevas consultas ERP.** Antes de guardar los bloques recibidos se ordenan las filas por la llave canónica de factura con un ordenamiento estable. Así se conservan las actualizaciones repetidas en el mismo orden y su última observación sigue reemplazando a las anteriores. La preparación valida la secuencia y recorre las facturas directamente, incluso si cruzan bloques recibidos, sin una segunda ordenación en SQLite.
- **Compatibilidad.** Los datos de cargas anteriores no se vuelven a descargar ni se marcan como ordenados. Las cargas API externas y Excel conservan el agrupador general cuando no tienen esa marca. La reaplicación de parámetros de una carga nueva copia su marca de ordenamiento junto con los bloques originales.
- **Menos normalización repetida.** Cada nombre distinto de columna se resuelve una sola vez por respuesta, manteniendo las comprobaciones de columnas equivalentes en conflicto.
- **Tiempos para el administrador.** El registro del servidor distingue descarga/lectura JSON del ERP, normalización, recepción de bloques y preparación/escritura de facturas. Solo registra identificadores internos, conteos y duraciones; no guarda credenciales, URL ni cuerpos de respuesta en estas trazas. El diagnóstico de solo lectura incluido muestra los nuevos controles si existen en la versión instalada.

## Integridad y recuperación

La escritura de facturas, detalles, cursor y contador sigue dentro de la misma transacción de Odoo. Se conservan el bloqueo por fuente, las restricciones de unicidad y la llave **compañía + TipoFactura + NumeroFactura**. No hay commits manuales. El programador de Odoo confirma cada llamada completada; su API de progreso permite continuar los trabajos pendientes. Esta entrega no altera la frecuencia configurada de los cron.

La publicación del corte sigue ocurriendo únicamente al terminar todas las facturas. El corte anterior permanece disponible durante la carga. Las distintas bodegas/productos de una factura se mantienen y un detalle repetido se reemplaza con su última observación. No cambian las fechas admitidas, las ciudades y reglas editadas, las toneladas/pallets, el análisis de transporte ni los filtros del tablero.

## Medición local

Se utilizó el archivo de referencia completo convertido en una respuesta ERP: **54.392 líneas, 44.989 facturas únicas y 383 pendientes**. El recorrido usa el parser, cálculos y métodos reales del módulo con un ORM simulado, sin servicio Odoo/PostgreSQL ni conexión al ERP. Incluye normalización, partición de la respuesta, preparación y construcción/carga simulada de valores; excluye la lectura inicial del XLSX de referencia.

Los bloques de escritura pasan de **450 a 90 (80% menos)** con los lotes de 500 permitidos por esa medición. La huella de todos los valores calculados de las facturas coincide antes y después. También coinciden las **1.030,61176 toneladas y 830,78 pallets pendientes**. Al duplicar el origen completo (108.784 líneas), se mantienen 44.989 facturas y 54.392 detalles únicos y se detectan 54.392 repeticiones, sin sumar nuevamente las cantidades.

En tres comparaciones secuenciales, la mediana del procesamiento local pasó de **15,23 s a 9,17 s (39,78% menos)**. Las mediciones de tiempo y su alcance están en `RENDIMIENTO_API_V1_8_5.json`. No constituyen una estimación de duración en producción: la descarga del ERP, la base PostgreSQL, el número de detalles por factura y la ocupación de los trabajadores pueden cambiar el resultado. Las trazas añadidas permiten medir esas fases en el servidor real.

Se aprobaron 239 pruebas Python autónomas. Se incluyen tres pruebas nativas adicionales de Odoo para la ruta ordenada, la preparación fallida después de crear un bloque y el rollback/publicación con cursor previo; deben ejecutarse en una base de pruebas Odoo con API Administrator. Los recursos de interfaz/estilos y el SQL de publicación se conservan byte por byte.

## Aplicar y continuar

1. Reemplazar la carpeta `transcash_dispatch_analysis` por la de este ZIP y reiniciar Odoo.
2. **Actualizar el módulo desde Aplicaciones y verificar 18.0.1.8.5.** Además de copiar los archivos, se deben agregar los campos `api_grouped_rows`, `background_batch_size` y `last_step_seconds`. No desinstalar el módulo. Las guardas de actualización rápida 1.7.1 se conservan: no se reconstruye el histórico completo al actualizar desde 1.6 o posterior.
3. Verificar que **Despachos: procesar importaciones por bloques** esté activo para usar los lotes adaptativos de segundo plano. La consulta automática del ERP sigue cada dos horas si la fuente está habilitada.
4. Recargar con Ctrl+F5. Si existe una carga recibida o parcialmente importada, abrir **Importaciones e histórico → Procesar / ver progreso** sobre esa misma carga. Se continúa su cursor; no volver a subir el Excel ni iniciar otra descarga.
5. Para la siguiente consulta usar **Sincronizar**. Las cargas nuevas aprovechan también la preparación directa sin SQLite. Una respuesta idéntica para el mismo corte continúa reutilizando la versión vigente.
