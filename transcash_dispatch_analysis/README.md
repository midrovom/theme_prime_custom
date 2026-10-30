# Transcash · Análisis de despachos para Odoo 18

Versión 18.0.1.8.4 del módulo, con importación del exportador Excel, consulta GET de getdatosdespachos mediante API Administrator y recepción por la API autenticada de Odoo. Compatible por diseño con Odoo 18 Community y Enterprise en servidor propio u Odoo.sh. Requiere validación de instalación en la base de destino. Odoo Online no admite este módulo Python.

## Recuperación de conexión y trabajo en segundo plano 1.8.4

Si el cron de importación está activo, la pantalla solicita el procesamiento y consulta el estado; las operaciones pesadas se ejecutan en el trabajador de Odoo. Si el cron está desactivado, se conserva el procesamiento interactivo con operaciones de hasta 100 facturas y un presupuesto de 500 líneas de detalle, sin dividir una misma factura. Los bloques preparados grandes de versiones anteriores se continúan con un cursor persistido.

Ante una pérdida de conexión, la pantalla vuelve a leer el avance confirmado antes de continuar. Hay reintentos acotados y un mensaje claro de reconexión, sin presentar la URL técnica como explicación al usuario. Las fechas, la llave comercial, el corte vigente y el cron de consulta de dos horas se conservan. Ver `docs/RECUPERACION_CONEXION_V1_8_4.md`.

Para retomar una carga ya recibida: instalar la actualización completa, recargar con Ctrl+F5 y abrir **Importaciones e histórico → Procesar / ver progreso**. No subir otra copia del Excel. Si sigue apareciendo literalmente el texto antiguo «Esta pantalla procesa los registros y muestra el avance», comprobar carpeta cargada, versión instalada y archivos del navegador con el diagnóstico incluido.

## Sincronización sencilla y progreso inmediato 1.8.3

El menú **Sincronizar** abre una pantalla breve con el botón **Sincronizar**. Fuente, método API, parámetros y resultados técnicos permanecen en Configuración; la operación usa la fuente configurada para la empresa activa. Al pulsar el botón se abre primero el avance y después comienza la recepción del ERP.

La pantalla muestra **Sincronización desde el ERP**, una barra animada durante la recepción/validación y el porcentaje real cuando ya se conoce el total de facturas. Usa **Facturas actualizadas** y **Registros del ERP**, también al reabrir una carga desde el histórico. Las importaciones Excel mantienen sus textos de archivo. La consulta por cron, la actualización por llave y los formatos de fecha se conservan. Ver `docs/SINCRONIZACION_SIMPLE_V1_8_3.md`.

## Formato de fecha del ERP 1.8.2

El conector GET reconoce **YYYY.MM.DD**, tal como `2026.01.05`, y lo convierte a `2026-01-05` (5 de enero). Se aplica a FechaFactura, UltimoDespacho y fecha_corte; admite hora opcional y conserva la validación de calendario. La representación con puntos produce la misma huella que la fecha ISO equivalente y mantiene la actualización única por tipo y número. Actualizar el módulo y ejecutar Sincronizar ahora; no hace falta cambiar el formato de la API.

## Fechas de SQL/PHP en la API 1.8.1

Se corrige el rechazo de fechas regionales como `05/01/2026 0:00:00` y de objetos DateTime de PHP. Se normalizan FechaFactura, UltimoDespacho y fecha_corte a ISO antes de procesar las facturas. El formato regional es **día/mes/año**: 05/01/2026 representa 5 de enero. Se admiten horas y fracciones de segundo; los timestamps con zona conservan su conversión a la zona de la operación. Si una fecha es inválida, se indica el campo y la línea del JSON. Ver `docs/FECHAS_API_V1_8_1.md`.

## Sincronización getdatosdespachos 1.8

Se usa el mismo esquema del módulo Inventario Inteligente suministrado: URL, ruta, usuario y contraseña centralizados en **API Administrator**, método GET y sus cabeceras habituales. Esta versión depende de `api_administrator` y `requests`; no requiere instalar Inventario Inteligente ni Comisiones.

Configurar una API GET activa llamada **getdatosdespachos** para la empresa, abrir **Configuración → Fuentes y API**, seleccionar la misma fuente usada para el Excel y activar **Sincronizar API cada 2 horas**. El menú **Sincronizar → Sincronizar** permite consultar bajo demanda a usuarios Operador/Responsable. La pantalla de progreso y el cron de importación continúan el trabajo por bloques. La configuración de origen muestra el último intento, respuesta válida, resultado y estado de importación.

Se mantienen las ciudades automáticas (Guayaquil 3 días calendario y las demás 9, conservando reglas editadas), la llave TipoFactura + NumeroFactura por empresa, las bodegas y productos distintos y una sola versión vigente por factura. Una respuesta sin cambios para el mismo corte reutiliza la importación vigente. Una respuesta fallida, vacía, incompleta según sus controles o con paginación declarada no sustituye los datos actuales. Las fechas del tablero no limitan la consulta al ERP.

Contrato y configuración: `docs/INTEGRACION_API_V1_8.md`. Respuesta de ejemplo: `examples/getdatosdespachos_response.json`. El conector está implementado y probado localmente; se debe configurar y comprobar contra el endpoint real en el servidor.

## Toneladas, pallets y totales por despachar 1.7.2

Se añaden **Toneladas por despachar** y **Pallets por despachar** a las tarjetas superiores. El resumen por plazo muestra las dos medidas y un Total por despachar que toma los mismos valores y filtros que esas tarjetas. Si redondear cada fila a dos decimales produce una diferencia, se presenta una línea de redondeo sin alterar los pesos originales.

El plan de vehículos identifica el total del resumen, lo incluido en el plan y lo excluido por modalidad. **Planificar todas las modalidades del resumen** permite igualar ambos alcances explícitamente. Se conservan el alcance inicial Solo Entrega Transcash y la actualización rápida de 1.7.1. Ver `docs/TARJETAS_TOTALES_V1_7_2.md`.

## Actualización sin reconstrucción repetida 1.7.1

Se corrige un proceso pesado que se ejecutaba en cada actualización del módulo: recorrer facturas y detalles históricos para normalizar llaves, pesos, pallets, bodegas y registros vigentes. En bases que ya completaron una versión 1.6 o posterior, las actualizaciones ordinarias omiten esa conversión. Las versiones anteriores conservan la conversión necesaria una sola vez mediante el mecanismo de migración por versión de Odoo. La validación/consolidación manual sigue disponible a petición del Responsable. Ver `docs/ACTUALIZACION_RAPIDA_V1_7_1.md`.

## Panorama inicial, plazos y pastel 1.7

Los filtros principales ocupan una barra compacta: Desde, Hasta, bodegas, favorito y Aplicar. Fuente, corte, ciudad y modalidad quedan en Más filtros; guardar vistas y los atajos de fechas están en Opciones. Los indicadores generales, el pastel y los pendientes por acuerdo aparecen antes del detalle de vehículos. Se mantiene la conservación de fechas al cambiar de vista.

**Pendientes por plazo de entrega** agrupa por los días y calendario SLA realmente aplicados a las facturas: 3, 9 o cualquier plazo configurado, con facturas pendientes, toneladas, en plazo, vencidas y por revisar. Permite abrir el grupo exacto. Muestra también lo que vence hoy y en los próximos tres días calendario desde cada corte.

El pastel usa el total facturado como referencia del 100%. En Facturas separa Con pendiente y Sin pendiente; en Toneladas separa Despachado y Pendiente sobre una base de pesos comparables, indicando la cobertura parcial cuando existe. No suma Facturado y Pendiente como dos partes independientes. Ver `docs/PANORAMA_PLAZOS_V1_7.md`.

## Conservar fechas al cambiar de vista 1.6.1

Cambiar de tablero o cargar un favorito desde el tablero conserva las fechas seleccionadas, aunque el favorito tenga otras fechas guardadas. También se conservan los rangos abiertos y Todas las fechas. Para cambiar el período, editar Desde/Hasta o pulsar Últimos 30 días o Todas las fechas. Se mantiene el inicio con los últimos 30 días al entrar al tablero.

## Tablero más claro y correcciones 1.6

Al entrar se consultan los últimos 30 días, incluido hoy, según la zona horaria del usuario de Odoo. Los indicadores y sus botones usan el rango aplicado. Se corrige el error de `map` al abrir facturas: las acciones devuelven la lista de vistas requerida por el cliente.

El plan distingue vehículos, viajes, días y contratación. Explica el cálculo por bodega y permite comparar una salida por bodega con la agrupación de carga para el mismo destino. La agrupación es un supuesto que debe incluir las recogidas en el tiempo de viaje; las reglas específicas de origen mantienen salidas separadas. Se conservan los valores de transporte editados por el usuario.

La carga tiene cuadros de toneladas facturadas, despachadas y pendientes, y pallets facturados y pendientes. El Excel actual no incluye PalletsFacturados; se muestra **Sin dato**. El campo opcional se admite en Excel/API. Los datos existentes se completan al actualizar, sin volver a importar. Ver `docs/TABLERO_CLARO_V1_6.md`.

## Corrección de estilos 1.5.1

Corrige el fallo de LibSass provocado por `min(420px,80vw)` en el selector de bodegas. Los dos estilos y su combinación se compilaron con LibSass 3.6.6. Reemplazar la carpeta, reiniciar Odoo, actualizar el módulo y recargar con Ctrl+F5. No requiere importar nuevamente los datos. Ver `docs/CORRECCION_ESTILOS_V1_5_1.md`.

## Registros únicos y bodegas múltiples 1.5

La llave comercial es **TipoFactura + NumeroFactura** por compañía. Una sola versión vigente entra en los totales, incluso con dos cargas del mismo Excel o fuentes superpuestas. Se conservan las versiones históricas separadas. El selector admite varias bodegas y recalcula sus toneladas y pendientes; la contratación usa únicamente el saldo pendiente. Se añaden toneladas despachadas y facturadas conocidas, resumen de vehículos por destino y un análisis nativo de bodegas con Favoritos de Odoo. La actualización completa los datos existentes; no requiere subir el archivo otra vez. Consultar `docs/UNICOS_BODEGAS_V1_5.md` y ejecutar **Validar / consolidar duplicados** para revisar la base instalada.

## Cumplimiento, toneladas y vehículos 1.4

El tablero muestra el cumplimiento del rango de fechas aplicado y las toneladas pendientes. El plan por ciudad y bodega de origen estima viajes, días de trabajo, tipos de vehículo, flota requerida y contratación adicional. Se pueden editar las capacidades, utilización, plazo objetivo, vehículos asignados y viajes completos por día, tanto en general como por destino. El plan comienza en Entrega Transcash y señala datos sin peso válido. Ver `docs/PLANIFICACION_V1_4.md` para fórmulas, actualización y supuestos. Las capacidades iniciales son ejemplos editables; no representan la flota real.

## Corrección de importación 1.2

Esta versión abre una pantalla que procesa los bloques y muestra su avance, sin depender del cron mientras esté abierta. Para continuar un Excel ya cargado, ir a Importaciones e histórico → Procesar / ver progreso. Ver `docs/CORRECCION_IMPORTACION_V1_2.md` para la actualización y recuperación de cargas en cola.

## Ciudades y plazos automáticos 1.3

Al importar por Excel o API se crean los plazos de las ciudades detectadas: **9 días calendario para todas y 3 para Guayaquil**. Los valores iniciales se aplican desde esa misma importación. Se pueden editar en **Configuración → Plazos por ciudad**; nuevas importaciones y actualizaciones del módulo conservan los cambios. Al actualizar también se completan las ciudades de las facturas ya importadas. Para recalcular un corte terminado, usar **Aplicar parámetros** y mantener abierta la pantalla de progreso. Ver `docs/CIUDADES_AUTOMATICAS_V1_3.md`.

## Funcionalidad

- Tablero de facturas únicas: pendientes, parciales, vencidas, cumplimiento exigible, cumplimiento de despachadas, promedio, mediana y P90.
- Ciudades creadas al importar, con plazos iniciales editables: 9 días calendario; Guayaquil, 3. Plazos por ciudad y condición de entrega, en días calendario o hábiles. Vigencia por fecha de factura y feriados configurables por compañía.
- Antigüedad de pendientes, peso, cajas y pallets pendientes. Priorización de vencidas y detalle por factura/bodega, con SKU si lo proporciona la fuente.
- Toneladas pendientes como KPI y medida de análisis; planificación por destino con capacidades y ciclos configurables.
- Constructor de visuales de barras, líneas, distribución circular y tablas. Tableros personales o compartidos con la compañía y orden configurable.
- Tabla dinámica, gráficos, filtros favoritos y exportación estándar de Odoo.
- Importación XLSX por bloques con progreso en pantalla, respaldo por cron, cortes históricos y activación del nuevo corte solo al terminar todos sus bloques.
- API por bloques con identificadores de lote y reintentos idempotentes.
- Perfiles Consulta, Operador y Responsable; reglas de acceso por compañía y tableros privados.

Las alertas son reglas de operación calculadas con los datos. El constructor ofrece indicadores y dimensiones definidos para despachos. No incluye DAX, relaciones entre fuentes arbitrarias, lenguaje natural ni el conjunto completo de funciones de Power BI.

## Base de esta entrega actualizada

Se usa exclusivamente `Analisis Despachos Trasncash(1).xlsx`: 54.392 registros por factura/bodega y 44.989 facturas distintas. El archivo no tiene SKU. La importación admite este consolidado y también el formato por producto/bodega cuando la fuente lo incluya.

Este archivo corrige las fechas: existen 17.743 registros con último despacho en un día distinto de la factura. El tiempo promedio observado es 1,65 días calendario para todas las modalidades y 9,28 días para Entrega Transcash. Estos promedios excluyen ajustes/devoluciones y observaciones de calidad. Ver el informe incluido para población, denominadores y límites.

Los plazos iniciales siguen la instrucción de negocio: 9 días calendario y 3 para Guayaquil. El cumplimiento se calcula con esos plazos, salvo donde existan reglas personalizadas, datos no evaluables o vigencias que no cubran la factura.

## Instalación

1. Confirmar que `api_administrator` está disponible en el servidor e instalar `requests` en su entorno Python si faltara. Copiar la carpeta `transcash_dispatch_analysis` a una ruta de addons de Odoo 18. No cambiar el nombre técnico de la carpeta.
2. Reiniciar Odoo, actualizar la lista de aplicaciones e instalar **Transcash · Análisis de despachos**.
3. Asignar el perfil del módulo a los usuarios. El administrador de Odoo recibe Responsable al instalar.
4. Revisar Configuración → Fuentes y API. La fuente inicial `TRANSCASH` pertenece a la compañía principal; crear otra fuente para otra compañía cuando corresponda.
5. Revisar Plazos por ciudad: Guayaquil inicia con 3 días y las otras ciudades se crearán con 9 al importar. Se pueden modificar días, calendario y vigencias. Una ciudad vacía representa la regla general; modalidad vacía representa todas las modalidades. Los feriados se configuran si se opta por días hábiles.
6. Importar el Excel completo o configurar getdatosdespachos siguiendo `docs/INTEGRACION_API_V1_8.md`. No hace falta reimportar Excel al actualizar una instalación existente. Para el archivo recibido, el corte analizado es **29/10/2026**.
7. Mantener abierta la pantalla de progreso hasta que termine. Para retomar una carga anterior, usar Importaciones e histórico → Procesar / ver progreso. El cron es un respaldo; la pantalla procesa los bloques aunque el cron no esté habilitado.
8. Si se cambian plazos después de importar, pulsar **Aplicar parámetros**. Se prepara otro corte con las reglas actuales y se mantiene el anterior como histórico.

Ejemplo desde una instalación con `odoo-bin`:

```bash
./odoo-bin -d base_prueba --addons-path=/ruta/odoo/addons,/ruta/custom_addons -i transcash_dispatch_analysis --stop-after-init
```

Después de reemplazar una versión ya instalada, reiniciar Odoo, actualizar el módulo desde Aplicaciones y recargar el navegador con Ctrl+F5.

No requiere paquetes Python adicionales. El lector XLSX usa la biblioteca estándar. Admite una hoja visible, archivos de hasta 40 MiB, contenido expandido de hasta 300 MiB y 500.000 líneas. El archivo recibido tiene 8,16 MiB y 54.392 registros. El proxy HTTP debe permitir una carga de al menos 64 MiB para cubrir la representación base64 del tamaño máximo admitido.

## Primera revisión del tablero

El filtro inicial consulta los últimos 30 días e incluye todas las condiciones de entrega. Seleccionar **Entrega Transcash** para analizar exclusivamente esa modalidad. El plan de vehículos comienza solo con Entrega Transcash. Los retiros de clientes siguen visibles y se pueden analizar por separado. **Todas las fechas** permite consultar el historial vigente completo. Cargar un favorito conserva las fechas que tienes seleccionadas en pantalla.

Una factura pendiente tiene al menos una línea con `Pendiente > 0,000001`. Una línea con saldo negativo no compensa el pendiente de otra línea. Se identifica por `TipoFactura + NumeroFactura` dentro de la compañía, conservando todas sus bodegas y productos distintos como detalle. Establecimiento y la columna Factura son descriptivos. Las fuentes y cortes conservan versiones; solo la observación vigente más reciente de esa llave entra en la operación.

Las facturas con registros de más de una bodega se agrupan en **VARIAS BODEGAS** para no duplicarlas. Las bodegas originales se conservan en el detalle de origen. No se suman cantidades heterogéneas de productos para fabricar un porcentaje de despacho.

El archivo actualizado está consolidado por bodega. Los cierres se evalúan al nivel recibido; no se puede demostrar cobertura de cada SKU ni reconstruir saldos positivos que ya se hayan compensado dentro del consolidado. Para ese control, la API debe proporcionar el detalle por producto.

## API

La consulta del ERP está implementada mediante **getdatosdespachos**, con cron de 2 horas y ejecución manual. Leer `docs/INTEGRACION_API_V1_8.md` y usar el JSON de ejemplo para implementar el método en origen.

Se reciben **cortes completos**, no eventos incrementales. La respuesta debe contener todo el universo de esa fuente y el detalle completo de cada factura, incluidas las ya despachadas. No enviar solo pendientes ni solo cambios. Una omisión sin controles no se puede detectar automáticamente; incluya `total_rows` y mantenga estable la extracción.

Cada corte conserva facturas, líneas y su origen (Excel o bloques JSON). Los históricos no participan en los totales vigentes. Los bloques preparados temporales se eliminan tras la activación; los cortes sin cambios del mismo día no crean otra versión. No hay borrado automático del histórico.

La recepción XML-RPC anterior sigue disponible. Leer `docs/CONTRATO_API.md`; `examples/push_api.py` envía JSON/JSONL autenticado con API key y credenciales desde variables de entorno.

## Pruebas

Las pruebas de cálculos y del conector con ORM/HTTP simulados se pueden ejecutar sin Odoo (con `requests` instalado):

```bash
python3 -m unittest discover -s transcash_dispatch_analysis/tests -p '*standalone.py'
```

Para las pruebas de integración incluidas, ejecutar en una base de prueba Odoo 18:

```bash
./odoo-bin -d base_prueba --addons-path=/ruta/odoo/addons,/ruta/custom_addons -i transcash_dispatch_analysis --test-enable --test-tags /transcash_dispatch_analysis --stop-after-init
```

La entrega no implica que se haya instalado el módulo en un servidor Odoo. Ver `docs/VALIDACION.md` para los controles realizados y pendientes.

## Referencias técnicas oficiales

- [Acciones de cliente Odoo 18](https://www.odoo.com/documentation/18.0/developer/howtos/javascript_client_action.html)
- [ORM Odoo 18](https://www.odoo.com/documentation/18.0/developer/reference/backend/orm.html)
- [Acciones programadas y procesamiento por bloques](https://www.odoo.com/documentation/18.0/developer/reference/backend/actions.html)
- [Seguridad de Odoo 18](https://www.odoo.com/documentation/18.0/developer/reference/backend/security.html)
- [API externa y API keys](https://www.odoo.com/documentation/18.0/developer/reference/external_api.html)
- [Restricciones de módulos Python en Odoo Online](https://www.odoo.com/documentation/18.0/developer/howtos/upgrade_custom_db.html)
