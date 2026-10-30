# Revisión de la demora al actualizar — 1.7.1

## Causa encontrada en el paquete 1.7

El archivo data/unique_records.xml llamaba a `_initialize_unique_records` sin noupdate. Por tanto, Odoo lo ejecutaba al instalar y en cada actualización, aunque solo cambiara un estilo o una pantalla.

El procedimiento recorría todas las compañías y sus importaciones históricas: consolidaba redundancias dentro de cada corte, normalizaba llaves, leía todos los detalles en bloques de 2.000, recalculaba pesos/pallets y sus cabeceras, completaba relaciones de bodegas y reconstruía los registros vigentes. También tomaba bloqueos transaccionales. Dos cargas completas podían representar 108.784 detalles y 89.978 versiones de factura, aunque solo 44.989 facturas vigentes entraran en los indicadores.

La creación de ciudades también agrupaba el histórico completo en cada actualización. Las dos operaciones son idempotentes en sus datos, pero repetirlas no era necesario y sí consumía lectura, escrituras y tiempo. Esta causa está comprobada en el código; sin el log ni acceso a la base no puede afirmarse qué consulta está ejecutando el servidor ahora.

## Corrección

Las llamadas XML masivas quedan bajo `noupdate="1"`, para la instalación inicial. La compatibilidad con datos antiguos se conserva mediante `migrations/18.0.1.7.1/post-10-legacy-data.py`, ejecutado por Odoo según la versión instalada.

| Versión instalada antes de actualizar | Conversión histórica al pasar a 1.7.1 |
| --- | --- |
| 1.6, 1.6.1, 1.7 o posterior | Ninguna. Estas versiones ya guardaron llaves únicas, pesos y pallets. |
| 1.3, 1.4, 1.5 o 1.5.1 | Una conversión para completar llaves, pesos, pallets y bodegas. |
| Anterior a 1.3 | Se completan las ciudades faltantes y luego los datos históricos, una vez. |
| Instalación nueva | Configuración inicial con tablas vacías, sin histórico que convertir. |

El criterio usa la versión instalada que Odoo pasa al script. Las versiones de módulo están completas con el prefijo 18.0. Una actualización fallida no debe marcarse manualmente como terminada; la transacción y el control de versión corresponden a Odoo. No se hacen commits parciales dentro del script. Una vez completada la conversión, las actualizaciones ordinarias no vuelven a recorrer todo el histórico.

La revisión manual **Validar / consolidar duplicados** se conserva. Ejecutarla solicita expresamente una revisión completa y puede tardar según el volumen; no se lanza por abrir el tablero ni por aplicar filtros. Se añaden trazas de inicio y fin por compañía para reconocer esa operación en el log.

El índice de unicidad, la llave TipoFactura + NumeroFactura, la selección de vigentes, las importaciones por bloques y los cálculos del tablero se mantienen. No hace falta subir el Excel otra vez. La configuración de capacidades y plazos editada por el usuario se conserva.

## Proceso programado

El cron `Despachos: procesar importaciones por bloques` es un respaldo de la importación. Solo busca cortes queued/loading y procesa un bloque por ejecución. No vuelve a importar ni recalcular cortes ready/archived y no es el encargado de actualizar el módulo. No se inicia una tarea remota desde ChatGPT.

## Aplicar la corrección y observar el servidor

Reemplazar la carpeta del módulo, reiniciar el servicio de Odoo y actualizar desde Aplicaciones. La actualización debe hacerse con esta versión cargada por el servidor; sustituir los archivos sin reiniciar no cambia el código de un proceso de actualización que ya estaba en marcha.

Si una actualización anterior sigue ejecutándose, no lanzar otra en paralelo. Revisar el log del proceso que ya está activo. Un reinicio del servicio requiere gestionar esa operación en el servidor. No borrar registros ni cambiar estados de ir.module.module para intentar forzar la finalización.

La corrección elimina el recorrido masivo repetido, pero no permite garantizar el tiempo total sin observar el servidor. El registro, las vistas, los recursos y los bloqueos de otras operaciones también forman parte de una actualización de Odoo.

`DIAGNOSTICO_ACTUALIZACION.sql` contiene consultas de solo lectura para un administrador de PostgreSQL: estado/versión del módulo, importaciones por estado y consultas activas con bloqueos. No cancela procesos ni modifica datos.

## Validación

148 pruebas Python locales. Las pruebas ejecutan el archivo real de migración con un entorno simulado y comprueban que desde 1.6 o posterior no se instancia el entorno de reconstrucción. También comprueban la ruta de descubrimiento del script y la protección de ambas llamadas XML. No se ha ejecutado la actualización ni SQL en el servidor del cliente.

Referencias oficiales de Odoo 18:

- https://www.odoo.com/documentation/18.0/developer/reference/upgrades/upgrade_scripts.html
- https://www.odoo.com/documentation/18.0/developer/reference/backend/data.html
