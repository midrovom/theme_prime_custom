# Registros únicos, toneladas y bodegas · 18.0.1.5.0

## Identidad y doble importación

La identidad de una factura es **TipoFactura + NumeroFactura**, dentro de la compañía. Establecimiento, bodega, Factura y fuente no añaden otra identidad comercial. Se conservan como datos descriptivos. La columna `Factura` no sustituye a `NumeroFactura`.

En las vistas operativas hay una sola versión vigente por esa llave. Excel y API preparan una nueva observación del documento: al terminar la carga, se publica la más reciente por fecha de corte y después por importación. Las observaciones anteriores quedan como versiones históricas y no se suman al tablero, las toneladas ni la contratación. Un índice único en PostgreSQL impide dos versiones marcadas como vigentes de la misma llave y compañía.

Si el mismo Excel se sube dos veces, habrá dos comprobantes de importación e histórico, pero el universo operativo seguirá teniendo una sola factura por llave. No se confunden las versiones históricas con duplicados operativos. Se puede consultar cada corte expresamente desde Importaciones e histórico.

Dentro de una misma carga se consolida una observación por factura/bodega, o por factura/bodega/producto cuando hay SKU. Las repeticiones idénticas no se suman. Si la misma clave de detalle vuelve con datos distintos, prevalece su última aparición y se registra el contador de actualizaciones. No se eliminan otras bodegas o productos de la misma factura. Si la API tiene varias líneas legítimas del mismo SKU en la misma bodega, debe incorporar un identificador estable de línea antes de usar este contrato.

## Resultado del archivo revisado

| Revisión | Resultado |
| --- | ---: |
| Registros del Excel | 54.392 |
| Facturas únicas por tipo + número | 44.989 |
| Facturas con varias filas de bodega | 7.149 |
| Filas adicionales legítimas por bodega | 9.403 |
| Filas idénticas repetidas | 0 |
| Repeticiones por factura y bodega | 0 |
| Bodegas de origen | 34 |
| Pendientes, todas las modalidades | 1.030,61176 t |
| Pendientes, Entrega Transcash | 767,22977 t |
| Peso despachado informado, todas las modalidades | 39.211,11937 t |

El Excel no requiere borrar filas: se perdería detalle real de bodegas si se dejara una sola fila física de origen por factura. El módulo consolida una cabecera por factura y conserva sus renglones de detalle únicos.

Se simuló una doble carga del conjunto completo: 89.978 observaciones se reducen a **44.989 facturas vigentes únicas**, con el mismo peso pendiente, sin duplicarlo. Esto comprueba el selector de versiones del módulo; no es una lectura de la base Odoo del cliente.

## Validar la base donde se hicieron las dos cargas

1. Actualizar el módulo. La actualización normaliza las llaves guardadas, completa bodegas y pesos desde el detalle original y vuelve a seleccionar las versiones vigentes únicas. Conserva cortes, archivos originales y plazos personalizados.
2. En el tablero, pulsar **Validar / consolidar duplicados**.
3. El resultado muestra las facturas vigentes, llaves duplicadas vigentes, versiones históricas fuera de los totales y redundancias consolidadas. Estos conteos sí proceden de la base donde se pulsa el botón.
4. Si solo se cargó dos veces este mismo universo y no hay otras fuentes, el esperado es 44.989 facturas vigentes y cero llaves duplicadas vigentes. El número histórico depende de cuántas cargas y recálculos se hayan realizado.

No hay conexión con la base del cliente desde el entorno de entrega. Los controles de PostgreSQL, permisos reales, actualización y montaje de la interfaz deben validarse en Odoo 18. Se incluye una consulta de diagnóstico de lectura en `VALIDAR_DUPLICADOS.sql`.

## Tres indicadores de toneladas

- **Pendientes**: kg pendientes de renglones con cantidad pendiente positiva / 1.000.
- **Despachadas**: suma de `PesoDespacho` / 1.000. Si ese peso falta en una línea con movimiento físico, se señala el faltante y el resultado conocido es parcial.
- **Facturadas conocidas**: `PesoFacturado` / 1.000 cuando lo informa la fuente. Si no hay ajustes y los pesos físico y pendiente son medibles, se puede conciliar como despachado + pendiente. Con ajustes/devoluciones se requiere el peso facturado explícito o `PesoAjusteDevolucion` para completar el total.

Este Excel no contiene PesoFacturado ni peso del ajuste. Hay **1.170 registros cuyo peso facturado no se puede completar** con los campos disponibles. Por eso la tarjeta se marca **Parcial**, con el número de registros pendientes de medición. No se extrapola el peso unitario de un consolidado que mezcla SKU. El subtotal facturado conocido no es comparable como total completo contra todo el peso despachado.

Para disponer de un total facturado completo desde la API, enviar `PesoFacturado` en kg por renglón único. La contratación nunca usa las toneladas facturadas ni las despachadas.

## Bodegas múltiples y planificación

El selector del tablero acepta varias bodegas con lógica O: incluye las elegidas. Todos los indicadores se recalculan únicamente con sus renglones, contando cada factura una vez. La lectura de una factura conserva su detalle completo para consultar el origen.

**Vehículos por destino** muestra toneladas pendientes, facturas únicas, tipos de vehículo y cantidad por tipo, número de viajes y días del escenario. Debajo se detalla cada bodega de origen y ciudad. Se conserva la separación de compañías y fuentes. Las rutas de origen independientes suman vehículos; no se supone que el mismo camión esté disponible simultáneamente para distintas rutas.

El plan arranca en Entrega Transcash dentro de los filtros seleccionados. Se puede ampliar el alcance. Solo considera cantidades pendientes positivas. Los renglones sin peso válido se señalan como estimación parcial; el archivo contiene 14 de estos renglones en Entrega Transcash. Capacidades, utilización, flota y ciclos siguen siendo configurables. No calcula costos, distancias, volumen ni restricciones viales.

Ejemplo real de alcance: al seleccionar únicamente las bodegas AGD y CDT, el pendiente de Entrega Transcash es **746,47762 t**, en lugar de tomar la carga de otras bodegas de las mismas facturas.

## Guardar vistas con Odoo

En **Toneladas por bodegas y destinos** se usan tabla dinámica, gráfico, lista, búsqueda, selección múltiple de bodegas y **Favoritos de Odoo**. Se guardan filtros y agrupaciones con el mecanismo nativo. El conteo de renglones de ese análisis es de detalles; no reemplaza al conteo único de facturas del tablero.

El tablero también tiene **Guardar vista en Favoritos**: guarda fechas, fuentes, corte, modalidad, ciudad, bodegas, alcance del plan y tablero elegido utilizando `ir.filters`, sin un almacén de favoritos paralelo. Esos favoritos del tablero se pueden recuperar desde su selector y aparecen en el análisis nativo asociado. Las modificaciones propias de visuales se guardan en Mis tableros.

## Actualizar

1. Reemplazar la carpeta `transcash_dispatch_analysis`, conservando ese nombre.
2. Reiniciar Odoo y actualizar el módulo desde Aplicaciones.
3. Recargar el navegador con Ctrl+F5.
4. Abrir el tablero y ejecutar **Validar / consolidar duplicados** para ver la comprobación de la base instalada.

No hace falta volver a subir el Excel. Se utilizan las líneas de origen ya guardadas. Las importaciones que estuvieran preparadas con la llave anterior se convierten a la nueva al continuar sus bloques.
