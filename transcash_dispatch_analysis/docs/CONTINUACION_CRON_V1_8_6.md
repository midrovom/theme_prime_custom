# Continuar la carga sin esperar otra ronda · 18.0.1.8.6

## Qué se encontró

La versión 1.8.5 redujo la normalización repetida y el número de bloques, pero su medición local no incluía las pausas del programador ni la escritura real en PostgreSQL. La llamada al cron seguía procesando un solo paso, normalmente hasta 500 facturas. Después devolvía el control.

En el código oficial Odoo 18 inspeccionado, el programador ejecuta como máximo diez llamadas por trabajo y ronda. Cuando todavía queda trabajo lo mantiene listo, pero los trabajadores vuelven a sondear aproximadamente cada minuto si no reciben otra notificación. Por ello, devolver el control noventa veces puede añadir varias rondas y pausas aunque los cálculos sean rápidos. No se ha confirmado que esa sea la única causa en el servidor del cliente: aún se necesitan sus tiempos reales para separar descarga, SQL, bloqueos y esperas.

## Corrección

Una llamada al cron ahora carga varios pasos completos. Devuelve el control al llegar a un presupuesto orientativo de **seis segundos**, al completar **veinte pasos**, al terminar el corte o ante un error/falta de avance. El tiempo se comprueba entre pasos; una factura excepcional o un paso lento puede superar el presupuesto antes de que vuelva a comprobarse. La preparación inicial se confirma por separado y no se encadena con la escritura masiva en esa misma llamada.

Si hubo trabajo y siguen existiendo cargas pendientes, se usa el `_trigger()` nativo de Odoo para solicitar la continuación inmediata. El aviso a los trabajadores se emite después de confirmar la transacción. No se notifica repetidamente cuando todas las fuentes están bloqueadas y no hubo trabajo. Las otras tareas mantienen su programación y pueden ejecutarse según la disponibilidad del servidor.

No se cambia el intervalo del cron de consulta ERP de dos horas, ni el intervalo/prioridad de los otros cron, ni límites globales de tiempo/memoria. El procesamiento del navegador mantiene sus operaciones cortas y consulta el avance confirmado.

## Datos y recuperación

Los métodos de escritura y publicación no cambian. La llave de factura sigue siendo **compañía + TipoFactura + NumeroFactura**. Se conservan las líneas distintas de bodega/producto; una repetición del mismo detalle se reemplaza. Toneladas, pallets, SLA, filtros y planificación mantienen sus cálculos.

Odoo confirma al terminar cada llamada del cron. En esa transacción quedan juntos los pasos completados, las facturas/detalles, sus cursores y contadores. No hay commits manuales. Si el proceso termina antes del commit, se revierten todos los pasos de esa llamada y la siguiente continúa desde la última llamada confirmada. Un error de datos atrapado por el importador revierte su paso, conserva el corte publicado anterior y detiene esa carga con su mensaje. Los problemas al solicitar una continuación se registran sin descartar el avance; la ejecución periódica permanece como respaldo.

## Resultado local y límite de la medición

Con las 54.392 líneas del archivo de referencia convertidas a filas del ERP, se conservaron exactamente **44.989 facturas**, **54.392 detalles**, **383 facturas pendientes**, **1.030,61176 toneladas** y **830,78 pallets pendientes**. Las llamadas del cron bajaron de **91 a 6** en la prueba y se solicitaron cinco continuaciones. Todos los valores calculados de factura tienen la misma huella antes y después. El origen completo duplicado mantiene esos mismos resultados y detecta 54.392 repeticiones.

Son ejecuciones de los métodos reales con ORM simulado. El trabajo local de cálculos/carga simulada tarda aproximadamente lo mismo; la corrección busca reducir rondas y esperas, **no se atribuye una nueva reducción de CPU**. Las rondas estimadas a diez llamadas y las posibles pausas son un modelo del programador, no tiempos observados en el servidor. Ver `VALIDACION_CRON_V1_8_6.json`.

Se aprobaron 251 pruebas Python autónomas. Se incluyen tres nuevas pruebas nativas Odoo de continuación, cursor y rollback completo para ejecutar en una base de prueba. No se ejecutaron esas pruebas nativas ni se conectó al ERP/Odoo del cliente. Los recursos de interfaz, cálculos, fechas, SQL de publicación y guardas de actualización rápida son idénticos a 1.8.5.

## Instalar y continuar la misma carga

1. Reemplazar la carpeta `transcash_dispatch_analysis` por la del ZIP. Reiniciar **todos los trabajadores Odoo** que usan esos addons, incluidos los del programador, para cargar el código nuevo.
2. Actualizar el módulo desde Aplicaciones y comprobar **18.0.1.8.6**. Desde 1.8.5 no se agregan campos ni se reconstruye el histórico. Desde versiones anteriores se conservan sus migraciones y controles ya incluidos. No desinstalar.
3. Verificar que **Despachos: procesar importaciones por bloques** esté activo y que exista un proceso con trabajadores de cron funcionando. Una casilla activa por sí sola no garantiza que haya un trabajador ejecutándola; la configuración puede estar en un proceso dedicado.
4. Abrir **Importaciones e histórico → Procesar / ver progreso** en la misma carga recibida. Se usa el avance confirmado, sin volver a subir el Excel ni descargar otra respuesta mientras esa carga esté en curso.

## Si persiste la demora

El administrador puede ejecutar `examples/diagnostico_rendimiento_odoo_shell.py` dentro de un Odoo shell con su configuración/base correctas. Es de solo lectura: muestra ruta y versión cargadas, presencia de la nueva lógica, configuración de trabajadores de ese proceso, estado del cron, últimas cargas y segundos sin avance/promedio incluyendo esperas. No solicita credenciales ni inicia importaciones.

Los logs ya separan `download_seconds`, `normalize_seconds`, preparación/escritura por paso y ahora `Dispatch cron steps=... remaining_snapshots=... seconds=...`. Comparar sus horas y duraciones permite identificar si la demora está en el ERP, en los pasos de base o entre ejecuciones. La salida de diagnóstico y ese tramo del log son necesarios para atribuir el tiempo restante del servidor real.

Referencias del programador inspeccionado: [ir_cron.py](https://github.com/odoo/odoo/blob/54c0991d2949bf4090231c8c167b4a1038769085/odoo/addons/base/models/ir_cron.py) y [server.py](https://github.com/odoo/odoo/blob/54c0991d2949bf4090231c8c167b4a1038769085/odoo/service/server.py).
