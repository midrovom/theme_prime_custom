# Validación de la entrega 18.0.1.8.6

## Continuación del programador 1.8.6

- 251 pruebas Python autónomas aprobadas: 239 anteriores y doce nuevas de varios pasos por llamada, límites de tiempo/pasos, preparación separada, cursor y reanudación, bloqueo de fuente, ausencia de trabajos/avance, error de datos, otra fuente pendiente y fallos del notificador/trigger. Se mantienen las comprobaciones de permisos, fechas, métricas y actualización rápida.
- Se inspeccionó el código oficial Odoo 18 en el commit 54c0991d2949bf4090231c8c167b4a1038769085: diez llamadas por ronda, sondeo de trabajadores de alrededor de un minuto sin otra notificación y `_trigger()` inmediato con aviso posterior al commit. El bloqueo de cron `FOR NO KEY UPDATE` permite la referencia del trigger sin bloquear su clave foránea. Es evidencia del código de referencia, no una lectura de la versión/configuración instalada del cliente.
- Archivo completo convertido en filas ERP: 54.392 líneas y 44.989 facturas; 91 llamadas del cron en 1.8.5 frente a 6 en 1.8.6, con cinco solicitudes de continuación. Igual huella de todos los cálculos, 383 pendientes, 1.030,61176 t y 830,78 pallets. Con el origen duplicado (108.784 filas) se conservan 44.989 facturas y 54.392 detalles, detectando 54.392 repeticiones. Se usa el modelo real con ORM simulado; las rondas a diez llamadas son un modelo del programador inspeccionado, no una medición de esperas en producción.
- Tres nuevas pruebas nativas incluidas para preparación/continuación, límites de pasos con reanudación y rollback de la transacción completa. No se ejecutaron porque no se dispone de un servicio Odoo/PostgreSQL de prueba operativo. Se incluye un diagnóstico de solo lectura para revisar el código realmente cargado, trabajadores, cron y tiempos en el servidor del cliente.
- No cambian los métodos de carga de facturas, cursores por bloque, parser de fechas, SQL de publicación/uniquidad, recursos de interfaz, permisos, esquema, cron XML ni guardas de migración. El registro y la confirmación de las transacciones siguen siendo responsabilidad de Odoo; no se agregan commits manuales.

## Rendimiento de importación API 1.8.5

- 239 pruebas Python autónomas aprobadas: 222 anteriores y 17 nuevas. Se comprueban igualdad de agrupación frente al motor general, actualización repetida que cruza bloques recibidos, orden estable, rechazo de una marca de ordenamiento incorrecta, compatibilidad de cargas antiguas, caché de columnas, límites adaptativos, factura excepcional completa, cursor antiguo y contexto de cron.
- El archivo de referencia completo se convierte a filas ERP y recorre los métodos reales del módulo con un ORM simulado: 54.392 líneas, 44.989 facturas, 383 pendientes, 1.030,61176 toneladas y 830,78 pallets pendientes. Coincide la huella de todos los valores calculados de factura antes/después. Los bloques de carga bajan de 450 a 90 cuando el trabajo medido permite lotes de 500. Ver `RENDIMIENTO_API_V1_8_5.json` para las mediciones y su alcance.
- Se repite la carga con 108.784 líneas (origen completo duplicado). Se conservan las mismas 44.989 facturas y 54.392 detalles, se detectan 54.392 repeticiones y coinciden las toneladas, pallets y huella de cálculos. No se está auditando la base instalada del cliente.
- Tres nuevas pruebas nativas Odoo incluidas para agrupación sin SQLite y reaplicación, rollback de preparación inválida y recuperación/publicación atómica con lotes de segundo plano. No se ejecutaron: el entorno local no tiene servicio Odoo/PostgreSQL. Las duraciones locales excluyen descarga ERP, escritura PostgreSQL, commits y competencia entre trabajos del servidor.
- Interfaz, estilos, cálculos comerciales, parser de fechas, publicación única, credenciales, cron XML y guardas de actualización rápida conservados. Se valida la sintaxis y referencias del paquete. No se reinstala ni se altera la programación configurada por el administrador.

## Reconexión y procesamiento acotado 1.8.4

- 222 pruebas Python autónomas: las 214 anteriores y ocho regresiones de cursor persistido, división de un bloque preparado de 250 facturas en 100/100/50, límite de líneas, integridad de una misma factura, cursor inválido, solicitud de trabajo en segundo plano, cron desactivado y permisos previos a la elevación. Se incluyen dos nuevas pruebas nativas Odoo para cursor/rollback y solicitud corta de procesamiento; no se ejecutaron porque no hay servicio Odoo/PostgreSQL local.
- 10 verificaciones nuevas del controlador con ORM y temporizadores simulados: cron activo sin llamadas pesadas del navegador, recuperación de lecturas perdidas, respuesta perdida después de un avance confirmado, límite de reintentos, separación de errores de negocio, respuesta perdida al solicitar el trabajo, solo lectura, salida de pantalla y reintento del mismo corte. Nueve regresiones anteriores también pasan, con recuperación automática después de una respuesta perdida.
- 14 verificaciones en Chromium real y componente OWL con RPC controlado. Se conservan las 12 de 1.8.3 y se añaden ejecución en segundo plano sin process_import_step desde el navegador y reconexión visual hasta 100%. Sin errores de página; capturas revisadas de aviso de reconexión y escritorio/móvil. El entorno no carga la base ni el servidor reales del cliente.
- Sintaxis, vistas, referencias y estilos se validan; LibSass 3.6.6 compila los estilos por separado y en conjunto. El nuevo campo processed_count se agrega a dispatch.chunk con valor inicial cero; no se reescriben facturas históricas. El adaptador de fechas, credenciales, llave, parámetros y publicación única se conservan.
- El mensaje del usuario demuestra una llamada interrumpida, pero no identifica si la causa fue proxy, red, reinicio, memoria o límite de tiempo del trabajador. Sin logs del momento no se afirma haber diagnosticado esa causa en el servidor. Se corrigen la dependencia de una llamada HTTP pesada y la recuperación del estado.

## Progreso inmediato y operación simple 1.8.3

- 214 pruebas Python autónomas aprobadas: se conservan las 208 anteriores y se añaden seis de apertura inmediata sin HTTP, RPC protegido de descarga, devolución de progreso persistido/errores, diálogo sin campos técnicos y textos/origen del ERP al reabrir. Se incluyen dos pruebas nativas adicionales (trece API en total), pendientes de ejecución en Odoo/PostgreSQL.
- 12 verificaciones con Chromium real y el componente OWL real, controlando las promesas RPC: barra visible mientras la descarga está pendiente, porcentaje solo tras conocer facturas, textos ERP sin Excel/archivo/endpoint, clics repetidos, error y reintento, respuesta sin cambios, reanudación desde histórico y cierre de pantalla. Sin errores de página. Se revisaron capturas de escritorio y móvil; a 390 px no hay desbordamiento horizontal. El servidor/cliente completo de Odoo no se cargó.
- Nueve regresiones del componente con servicios simulados: procesamiento de Excel, bloqueo ocupado, reintento y recuperación de conexión, solo lectura, doble clic y salida de pantalla. El nuevo estilo se compila con LibSass 3.6.6; sintaxis Python/XML y referencias de manifiesto se validan.
- Se conservan el adaptador de fechas 1.8.2, cron, SQL de registros vigentes, métricas, ciudades, planificación y guardas de actualización rápida. No se ha accedido al servidor ni a la API real en esta validación. La barra inicial es indeterminada, no un porcentaje estimado de bytes descargados.

## Formato YYYY.MM.DD 1.8.2

- 208 pruebas autónomas aprobadas: las 203 anteriores y cinco regresiones nuevas del formato exacto comunicado por el usuario. Se cubren los campos en minúsculas, FechaFactura, UltimoDespacho, fecha_corte, hora opcional, fracciones, objetos PHP y zona explícita.
- `2026.01.05` se convierte a `2026-01-05`; `2026.05.01` se convierte a `2026-05-01`. Se comprueba igualdad de registros/huellas con ISO, rechazo de calendario inválido, fecha futura y error con número de línea. La normalización solo cambia el prefijo de fecha, conservando los puntos de las fracciones de segundo.
- El cron, modelos, permisos, esquema, publicación de versiones y archivos de interfaz/estilos se conservan sin cambios respecto a 1.8.1. No se ha accedido al servidor ni al endpoint real; las once pruebas nativas API incluidas siguen pendientes de ejecución en Odoo/PostgreSQL.

## Fechas SQL/PHP 1.8.1

- 203 pruebas Python autónomas ejecutadas; se conservan las 194 anteriores y se añaden nueve casos de regresión con subcasos de fecha regional, hora 0:00:00, fracciones SQL Server, objetos PHP, fecha nula/blanca, zonas horarias, formatos inválidos, error con número de línea, fecha de corte, campos en minúsculas y estabilidad de la huella entre representaciones equivalentes.
- Se reprodujo el error exacto de 1.8 con `05/01/2026 0:00:00` y con un objeto PHP de fecha. Ambos se normalizan ahora al mismo valor ISO; el orden regional se fija en día/mes/año. Las fechas imposibles se siguen rechazando y no se sustituyen por hoy.
- Se añade una prueba nativa a tests/test_api_sync_odoo.py para comprobar fechas normalizadas en factura/detalle y su fecha límite SLA. Las once pruebas nativas API incluidas siguen pendientes de ejecución en Odoo/PostgreSQL; las pruebas locales usan servicios simulados. No se ha conectado al servidor ni a la API real del cliente.
- Sin cambios de campos, esquema, cron, ciudades, llaves comerciales, publicación ni archivos de interfaz/estilos respecto a 1.8. Solo cambia el adaptador de fechas, manifiesto, pruebas y documentación. Se conservan los guardas de actualización rápida.

## Conector GET y programación 1.8

- 194 pruebas Python autónomas ejecutadas: se conservan las 156 anteriores y se añaden 38 de contrato JSON, autenticación/cabeceras, búsqueda exacta por empresa, errores, límites, protección frente a paginación, fechas locales, actualización por llave, cambios/reversiones, ausencia de cambios, bloqueo entre consultas, permisos previos a la elevación y cron de dos horas por empresa.
- Con el archivo original completo se simula el cuerpo JSON de getdatosdespachos: 54.392 líneas, 44.989 facturas únicas, 383 pendientes, 1.030,61176 toneladas y 830,78 pallets pendientes. Las métricas coinciden con la lectura Excel y concilian por plazo. Reordenar o duplicar el feed completo conserva la huella de datos efectivos. Se usan los parámetros iniciales, no la configuración ni base remota del cliente.
- Se incluyen diez pruebas nativas nuevas en tests/test_api_sync_odoo.py para ejecutar en Odoo/PostgreSQL: sustitución de pendientes y cierre, históricos, detalle de bodegas, ciudades, carga repetida, error, rollback de bloques, permisos y configuración única. No se han ejecutado esas pruebas nativas porque el entorno local no tiene servidor Odoo/PostgreSQL ni API Administrator instalado. Los 194 casos anteriores usan ORM y HTTP simulados.
- Dependencia api_administrator confirmada en el manifiesto del módulo de referencia adjunto. Se reutilizan sus campos y cabeceras GET. No se modificó ese módulo ni sus archivos. No se consultó el ERP real ni se validaron sus credenciales/respuesta.
- Se conserva byte por byte la interfaz/estilos del tablero 1.7.2 y los guardas de actualización rápida 1.7.1. La nueva programación es noupdate=1 y no realiza consultas HTTP durante la actualización. Las nuevas columnas son de configuración/trazabilidad, sin conversión histórica automática.

## Tarjetas y conciliación 1.7.2

- 156 pruebas Python. Se añaden totales de toneladas/pallets por acuerdo, inclusión de Sin plazo, disponibilidad parcial de pallets, redondeo positivo/negativo, separación de modalidades y diferencias de detalle del plan. Se comprueba el mismo total al seleccionar varias bodegas. Se conservan las pruebas de actualización rápida.
- 38 comprobaciones con el componente real montado en OWL/jsdom: ocho tarjetas superiores, valores iguales al total de plazos, clic en pendientes, preservación de fechas y cambio explícito del alcance del plan.
- 13 verificaciones en Chromium real con RPC simulado: tarjetas, totales visibles, presentación en 1440×900, 1366×768 y 390×844, opciones del plan, apertura de facturas y redondeo de los grupos reales del Excel. Se revisaron capturas del panorama y la fila de redondeo. El tema y servidor de Odoo del cliente no se cargaron.
- Lectura completa del archivo: 1.030,61176 t y 830,78 pallets pendientes concilian con sus grupos. Se reproduce la diferencia de redondeo de 0,01 t al sumar las dos filas redondeadas del archivo completo y se muestra su ajuste. Para 30/09–29/10, 871,63914 t del resumen = 620,42012 t Entrega Transcash + 251,21902 t de otras modalidades. Con el alcance Todas las modalidades filtradas, el plan coincide con el total del resumen. También se valida la selección exclusiva de Entrega Transcash.
- Sintaxis Python/XML, referencias y manifiesto validados; ambos SCSS se compilan con LibSass 3.6.6. No hay cambios en el esquema, la importación o el mecanismo que evita reconstrucciones históricas al actualizar. Sin acceso a la base remota del cliente.

## Rendimiento de actualización 1.7.1

- 148 pruebas Python, incluidas ocho nuevas comprobaciones de la actualización: se ejecuta el archivo real de migración con servicios simulados. Desde 1.6/1.6.1/1.7 y posteriores no se instancia un entorno de conversión ni se leen facturas. Desde 1.3–1.5 se conserva la conversión de datos única; desde versiones anteriores se completan primero las ciudades.
- Se comprueba que las llamadas XML de inicialización masiva están bajo noupdate=1 y que la ruta del post-script coincide con la versión del manifiesto. Las versiones históricas desconocidas conservan una ruta prudente de conversión; las instalaciones nuevas usan su inicialización XML sin histórico.
- Sintaxis, datos XML, manifiesto, permisos y referencias de vistas validados. La interfaz y estilos conservan los archivos de la versión 1.7 ya probada; solo cambian inicialización, selección de migraciones, trazas y documentación.
- No se ha accedido al servidor del cliente ni se ha medido su actualización real. La ejecución del cargador de migraciones y del SQL sobre PostgreSQL debe verificarse al actualizar su base. No se promete una duración fija: Odoo puede seguir necesitando tiempo para sus vistas, registro, recursos y bloqueos existentes.

## Panorama y acuerdos 1.7

- 140 pruebas Python sin Odoo, incluyendo nuevos casos de grupos de acuerdos, calendarios diferentes, cero días, ajustes, próximos vencimientos por fecha de corte, porcentajes sin solapamiento, pesos incompletos/no conciliados y acciones de detalle con la misma población. Se comprueban también el desglose por bodegas y las toneladas comparables de la selección múltiple.
- 34 comprobaciones con el XML y componente reales montados en OWL 2.8.1 y jsdom: filtros adicionales plegados, cambio de pastel, cobertura parcial, grupos de 3/9 días, botón de grupo, preservación de fechas/favoritos y regresiones del tablero.
- Navegador Chromium 153.0.8010.0 real con el componente OWL y SCSS compilado, datos ilustrativos y RPC simulado: filtros superiores de 54 px en resoluciones 1440×900 y 1366×768; indicadores, pastel y tabla de acuerdos visibles en la primera pantalla de esas pruebas. Inspección de capturas de escritorio y 390×844, sin desbordamiento horizontal del documento. Se prueban los eventos de Más filtros, pastel por toneladas y detalle por acuerdo. La prueba usa una cabecera ilustrativa; no sustituye la instalación con el tema y cliente completo de Odoo.
- LibSass 3.6.6 compila ambos estilos del módulo y su concatenación.
- Auditoría del XLSX original con las reglas iniciales de referencia: 44.989 facturas, 383 pendientes y 1.030,61176 t conocidas. Acuerdo de 3 días: 115 pendientes; acuerdo de 9 días: 268. En 30/09/2026–29/10/2026: 5.222 facturas, 281 pendientes, repartidas en 50 de 3 días y 231 de 9 días. Los grupos, toneladas pendientes y pastel por facturas concilian con sus KPI. La base comparable de peso cubre 4.687 de esas 5.222 facturas y se marca parcial. Estas cifras son del archivo recibido y no de una consulta a la base remota.
- Sintaxis, manifiesto, referencias de vistas y permisos. La instalación, las pruebas nativas añadidas y el tema de Odoo del cliente siguen pendientes de validación en su servidor.

## Corrección de fechas 1.6.1

Se comprueba con el componente y XML montados en OWL que cambiar de favorito o tablero conserva el rango actual. Se cubren el rango inicial de 30 días, un rango personalizado, solo Desde, solo Hasta y Todas las fechas; se usan favoritos con fechas diferentes guardadas y sin fechas. Los eventos reales de los selectores conservan los valores de los inputs y el período enviado a la consulta de datos. Los botones explícitos de fechas siguen pudiendo cambiarlo. Las fechas guardadas del favorito original no se modifican. Las pruebas son locales con RPC simulado, sin acceso al servidor del cliente.

## Ejecutado en 1.6

- 125 pruebas Python independientes: se añaden el caso ilustrativo de 27,95 t, agrupación por destino, restricciones por bodega, días con flota necesaria, pallets ausentes/cero/negativos, fechas de 30 días inclusivos y acciones de todos los indicadores con su lista de vistas.
- Montaje y renderizado real del componente y su XML con OWL 2.8.1 y jsdom 26.1.0: 17 verificaciones de inicialización, fechas antes de la primera consulta, cinco cuadros de carga, pallets facturados sin dato, click real en un indicador, cambio real del selector de agrupación, favoritas, períodos, análisis dinámico, manejo de errores y compilación del XML de progreso. Los servicios RPC/acciones se simulan; no equivale a una sesión completa del cliente Odoo.
- Compilación real de ambos SCSS y del conjunto con LibSass 3.6.6. Se conserva la corrección 1.5.1.
- Lectura del XLSX completo con el motor actualizado: 54.392 registros, 44.989 facturas únicas, 1.030,61176 t pendientes en todo el archivo. Las 54.392 filas carecen de PalletsFacturados y contienen PalletsPendientes. El indicador facturado se distingue como ausente.
- Rango de comprobación 30/09/2026–29/10/2026: 5.222 facturas únicas. Entrega Transcash: 55 pendientes y 620,42012 t conocidas, idénticas con salidas por bodega o agrupadas por destino. Hay seis filas pendientes sin peso válido; ambos modos conservan la advertencia parcial. Son cifras del archivo recibido con reglas de referencia, no una consulta de la base del cliente.
- Validación estática de Python, XML, vistas, permisos y manifiesto. Se incluyen pruebas nativas de actualización de pallets y acciones filtradas para ejecutarlas en Odoo.

## Validación histórica 1.5

## Corrección 1.5.1

Se reprodujo el fallo de compilación del SCSS del paquete 1.5 con LibSass 3.6.6. La corrección se conserva y se incluyen el detalle y el comprobador en CORRECCION_ESTILOS_V1_5_1.md y tests/check_styles.py. No se han compilado los demás módulos del servidor del cliente.

## Ejecutado

- 108 pruebas Python sin servidor Odoo: reglas SLA, ciudades, importaciones por bloques, deduplicación de detalles, llave TipoFactura + NumeroFactura, selección de versiones publicadas, conservación de bodegas, pesos, ciclos y métodos reales del tablero con un ORM de lectura en memoria.
- En la entrega 1.5 se ejecutaron 10 verificaciones JavaScript de bodegas múltiples, favoritos, formatos, parcialidad y auditoría. La interfaz 1.6 tiene la validación de montaje y eventos descrita arriba.
- Lectura completa del XLSX vigente: 54.392 registros, 44.989 llaves comerciales, 7.149 facturas con varias filas de bodega, 34 bodegas, cero filas idénticas y cero repeticiones factura/bodega.
- Doble carga simulada del universo completo con el selector de publicación que usa el módulo: 89.978 versiones -> 44.989 vigentes; el pendiente se conserva en 1.030,61176 t y no se duplica.
- Recorrido completo de lectura, preparación y carga con los métodos reales del modelo y ORM en memoria: 44.989 facturas, 54.392 renglones, 383 pendientes y 100 pendientes Entrega Transcash, con 73 ciudades y progreso monótono.
- Selección real de dos bodegas (AGD/CDT): se conciliaron 746,47762 t pendientes de Entrega Transcash y sus destinos, excluyendo el peso de otras bodegas.
- Sintaxis Python/JavaScript/XML, referencias de campos, archivos del manifiesto, 15 modelos y 26 filas de permisos declarados.

## Por comprobar en la base Odoo del cliente

- No se ha consultado ni modificado la base remota del cliente. La sospecha de duplicación por sus dos cargas debe comprobarse con el botón Validar / consolidar duplicados después de actualizar.
- Instalación/actualización y ejecución de las pruebas de integración nativas incluidas con Odoo 18 y PostgreSQL. Incluyen dos cargas, fuentes superpuestas, favoritos, bodegas y conversión de datos anteriores.
- Ejecución real del índice parcial único, SQL de actualización de datos previos, transacciones, concurrencia y permisos ir.filters con usuarios reales.
- Sesión completa del cliente web Odoo con el tema del cliente. En 1.7 se probó el componente en Chromium local y se revisaron capturas de escritorio/móvil con datos ilustrativos; no se ha cargado el servidor Odoo remoto.
- Capacidades reales de carga, ciclos de ruta, volumen, acceso y disponibilidad de flota antes de contratar.

Los cortes históricos se conservan como versiones explícitas fuera de los totales operativos. La entrega no afirma una limpieza ya ejecutada en el servidor del cliente. Ver UNICOS_BODEGAS_V1_5.md para actualizar y verificar esa base sin subir el Excel otra vez.
