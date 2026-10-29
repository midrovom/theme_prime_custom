# Cumplimiento, toneladas y capacidad por destino · 18.0.1.4.0

> Esta documentación describe la base de planificación 1.4. La versión 1.5 añade llave única, pesos facturados/despachados, bodegas múltiples y Favoritos: consultar UNICOS_BODEGAS_V1_5.md.

## Qué cambia

- El encabezado muestra **Cumplimiento del período**, sus fechas y el numerador/denominador. Las fechas Desde/Hasta seleccionan facturas por fecha de emisión; el estado sigue siendo el registrado a la fecha de corte. No se reconstruye un estado histórico a la fecha Hasta a partir de un corte posterior.
- Se muestran **toneladas métricas pendientes** en una tarjeta, la tabla de ciudades, la lista de facturas y el análisis dinámico. El constructor de visuales ofrece Toneladas pendientes. Conversión exacta: kg / 1.000.
- El plan muestra toneladas, viajes, días con la flota del escenario, vehículos necesarios para un plazo objetivo y adicionales por contratar. Se desglosa por ciudad **y bodega de origen**, manteniendo separadas compañías y fuentes.
- Cada fila permite comparar los tipos de vehículo. La sugerencia prioriza menos vehículos dentro del objetivo, después menos viajes y después menor capacidad sobrante. No calcula costos ni combina tipos dentro de una misma ruta.

## Actualizar

1. Reemplazar la carpeta `transcash_dispatch_analysis`, conservando su nombre técnico.
2. Reiniciar Odoo, actualizar el módulo desde Aplicaciones y recargar el navegador con Ctrl+F5.
3. Abrir el tablero. **No hace falta volver a importar el Excel** para las toneladas o el plan: se usan las facturas y líneas guardadas.
4. Revisar Configuración → Plan de despacho, Tipos de vehículos y Capacidad por destino. Volver al tablero y pulsar Actualizar.
5. Si el corte anterior todavía no tenía aplicados los plazos de ciudad de la versión 1.3, usar Aplicar parámetros y completar el progreso. Los cambios de capacidad solo requieren actualizar el tablero.

## Configuración inicial editable

| Parámetro | Valor de referencia |
| --- | --- |
| Plazo de planificación para vaciar pendientes | 3 días operativos |
| Vehículos asignados | 1 por ruta de origen y destino; es un escenario, no un inventario real de flota |
| Viajes completos por vehículo y día operativo | 1 |
| Tipos de vehículo | Camión 3,5 t; 5 t; 10 t; 15 t; tráiler 28 t |
| Utilización prevista de cada tipo | 90 % de la capacidad de carga |
| Alcance inicial del plan | Entrega Transcash dentro de los filtros del tablero |

Las capacidades son referencias editables, no capacidades certificadas ni límites legales. Se debe registrar la capacidad real del vehículo que se contratará. Se conservan los valores editados y vehículos archivados al actualizar el módulo. Al crear una fuente para otra compañía se inicializa su escenario si no existía.

El selector **Planificar** permite incluir todas las modalidades filtradas cuando se requiera. Por defecto los retiros de clientes y otras modalidades no generan una recomendación de contratación Transcash. El KPI principal de toneladas siempre conserva el alcance de los filtros generales; la tarjeta Carga del plan identifica el alcance de contratación.

En **Capacidad por destino** se puede fijar el tipo de vehículo, días objetivo, flota asignada y viajes por día para una ciudad. Una regla con código de bodega tiene prioridad sobre una regla general de ciudad. Un vehículo preferido archivado deja esa ruta sin estimación hasta corregir su configuración. Las reglas de destino reemplazan los valores generales para esas rutas.

Los días de planificación son **días operativos de trabajo** desde que la carga está disponible. No son días de atraso ni reemplazan el SLA de 3 días calendario de Guayaquil y 9 de las demás ciudades. No se genera una fecha de llegada ni se usa distancia o tráfico.

## Fórmulas

1. Carga útil por viaje = capacidad de carga en t × utilización / 100.
2. Viajes = redondear hacia arriba (kg pendientes / carga útil en kg).
3. Viajes posibles por vehículo en el objetivo = parte entera (días objetivo × viajes por día).
4. Vehículos requeridos = redondear hacia arriba (viajes / viajes posibles por vehículo).
5. Adicionales = máximo (vehículos requeridos − vehículos asignados, 0).
6. Días con flota asignada = redondear hacia arriba (redondear hacia arriba [viajes / vehículos asignados] / viajes por día).

Los viajes deben incluir carga, recorrido, entrega y regreso. Un valor 0,5 significa un viaje completo cada dos días. Si el objetivo es menor que el ciclo de un viaje no se informa una cantidad ficticia de vehículos: se solicita aumentar el horizonte. Con cero vehículos asignados se informa la necesidad de contratación y los días con la flota actual quedan sin estimación.

El total de días usa el máximo de los días por ruta, suponiendo rutas en paralelo y flotas independientes. El total de vehículos suma las rutas; el mismo camión no se reutiliza en dos rutas del escenario. No es una programación optimizada para compartir flota entre ciudades ni una recomendación de compra de vehículos.

Ejemplo: 54 t, camión de 10 t, utilización 90 %, un viaje al día, un vehículo asignado y objetivo de 3 días. Se necesitan 6 viajes, 6 días con ese vehículo, o 2 vehículos en total para cumplir el objetivo de 3 días; 1 sería adicional.

## Calidad y límites

Se cuenta la factura una vez en el KPI. Una factura con pendientes en varias bodegas aparece en varias rutas; los conteos de facturas por ruta no deben sumarse como facturas únicas.

Las líneas pendientes con peso vacío, cero, negativo o no finito se señalan. Una ruta sin ciudad, sin origen, sin un peso calculable o sin tipos de vehículos activos no recibe recomendación. Los ajustes y observaciones de calidad se indican para revisión; sus pesos positivos se conservan. Si parte del plan no puede calcularse, el tablero indica cuántas rutas cubre la estimación y muestra los subtotales calculables. No presenta esos subtotales como capacidad suficiente para toda la demanda.

El archivo de referencia contiene **14 registros pendientes de Entrega Transcash sin peso positivo**. Las toneladas conocidas sí concilian: **1.030,61176 t** en todas las modalidades y **767,22977 t** en Entrega Transcash. No se supone que el peso desconocido sea cero trabajo.

El cálculo considera peso. Antes de contratar se debe validar volumen, posiciones de pallets, acceso al destino, dimensiones, restricciones viales, tiempo de descarga y ciclo real. No hay cotizaciones de transportistas en el archivo.

## Cumplimiento del período

Cumplimiento = despachadas evaluables a tiempo / (despachadas evaluables + pendientes vencidas evaluables) × 100, dentro del rango y los filtros aplicados. Las pendientes aún en plazo quedan fuera del denominador. Ajustes y registros no evaluables se presentan por separado. Si no hay denominador, aparece Sin medición.

El período y los cálculos se devuelven juntos desde el servidor; editar los controles no cambia los resultados hasta pulsar Aplicar filtros. Se conservan los parámetros capturados en cada corte y las configuraciones SLA personalizadas.
