# Definiciones de los indicadores

## Unidad de análisis y población

Se cuenta una factura por la combinación `TipoFactura`, `NumeroFactura` y `Establecimiento`, dentro de una compañía, fuente y corte. El archivo actualizado tiene una fila por factura/bodega y no incluye SKU. La importación también admite producto/bodega. Las filas de detalle no son facturas nuevas. Los filtros por fecha se aplican a la **fecha de factura**. Los gráficos mensuales son cohortes de facturación, no meses del movimiento de despacho.

El estado de cada factura es el registrado en el corte. El atraso se evalúa a la fecha de extracción. Un archivo histórico no se presenta como el pendiente actual ni se extrapola a hoy. Al seleccionar un corte histórico se usa su estado y sus reglas capturadas.

## Indicadores

| Indicador | Cálculo |
| --- | --- |
| Facturas analizadas | Número de facturas distintas en los filtros seleccionados. |
| Pendientes | Facturas con al menos una línea con `Pendiente > 0,000001`. |
| Parciales | Pendientes con alguna cantidad de despacho físico en cualquier línea. |
| Vencidas | Pendientes evaluables cuya fecha límite es anterior a la fecha de corte. |
| Vencen al corte | Pendientes evaluables con fecha límite igual al corte. Siguen dentro de plazo hasta el fin de ese día. |
| Tiempo de despacho | Fecha del despacho completo menos fecha de factura, en días calendario. Solo cierres físicos con fechas medibles y sin observaciones de calidad. |
| Promedio | Suma de tiempos medibles / número de facturas con tiempo medible. |
| Mediana | Percentil 50 de los tiempos medibles. |
| P90 | Percentil 90 con interpolación lineal entre observaciones ordenadas. |
| Cumplimiento de despachadas | Despachadas evaluables a tiempo / despachadas evaluables × 100. |
| Cumplimiento exigible | Despachadas evaluables a tiempo / (despachadas evaluables + pendientes vencidas evaluables) × 100. |
| Peso/cajas/pallets pendientes | Suma de esos campos sobre líneas con pendiente positivo. |
| Toneladas pendientes | Peso pendiente en kg / 1.000, dentro de los mismos filtros. |
| Antigüedad | Corte menos fecha de factura, en días calendario, para las pendientes. |

Cuando el denominador es cero, el porcentaje aparece **Sin medición**, no 0%. El porcentaje global se calcula desde su numerador y denominador; no es un promedio de porcentajes de ciudades o meses.

El **Cumplimiento del período** es el cumplimiento exigible dentro de las fechas de factura Desde/Hasta aplicadas. El estado sigue siendo el de la fecha de corte. Para días de trabajo y vehículos por destino, consultar `PLANIFICACION_V1_4.md`; son escenarios de capacidad y no métricas SLA históricas.

Ejemplo: 80 despachadas a tiempo, 20 despachadas tarde y 10 pendientes vencidas producen 80% de cumplimiento de despachadas y 72,73% de cumplimiento exigible. Las pendientes que aún están en plazo no afectan esos denominadores.

## Fecha de cierre y ajustes

Para un despacho completo, todas las líneas deben estar físicamente cubiertas, sin pendiente positivo y sin ajustes/devoluciones. La fecha de cierre es el máximo `UltimoDespacho` de las líneas físicamente despachadas. Se exige fecha para toda línea con despacho físico.

Un saldo cerrado por devolución no se toma como evidencia de despacho físico. En esta primera versión, las facturas con cualquier ajuste/devolución se presentan separadas y se excluyen de los KPI de cumplimiento. Se conservan en el conteo de pendientes cuando todavía tienen saldo por despachar.

Los errores de fechas, ciudades, saldos negativos, cantidades que no concilian, duplicados producto/bodega e inconsistencias de cabecera se señalan y excluyen del cumplimiento. Los valores originales siguen disponibles para revisión. Los errores Excel en campos descriptivos se conservan con su celda y no invalidan cantidades o fechas.

## Parámetros

- Las ciudades de Excel y API se crean automáticamente con 9 días calendario, excepto Guayaquil con 3. Se normalizan mayúsculas, tildes y espacios para evitar duplicados. Los valores iniciales cubren facturas desde 01/01/1900 y todas las modalidades.
- Los plazos se editan en Configuración → Plazos por ciudad. Una ciudad con una regla propia conserva sus días, calendario, vigencias y estado archivado; las importaciones no restablecen valores iniciales. Las reglas por ciudad y modalidad mantienen su prioridad.
- El día de factura es día cero. Un plazo de cero vence el mismo día.
- Calendario suma todos los días. Hábiles cuenta lunes a viernes y omite los feriados configurados para esa compañía.
- La fecha límite vence al final del día. El Excel no contiene hora de despacho; no permite prometer tiempos exactos en horas.
- Prioridad: ciudad + modalidad; ciudad; modalidad general; regla general. Reglas de igual prioridad con vigencias superpuestas se rechazan.
- La vigencia se compara con la fecha de factura. Al importar se capturan reglas y feriados; cambiar parámetros no reescribe el histórico.
- **Aplicar parámetros** prepara un nuevo corte con las reglas actuales y lo activa al terminar. Para que una regla nueva evalúe facturas antiguas, su vigencia debe cubrir esas fechas.

Los feriados no se descargan automáticamente y no se suponen calendarios regionales. El inicio es la fecha de facturación; si el negocio exige contar desde aprobación del crédito, liberación de bodega u otra autorización, ese campo debe incorporarse al contrato de la API.

## Límites de los datos

El archivo actualizado es una fotografía consolidada con último despacho por bodega. No contiene SKU y el cierre físico refleja las cantidades del consolidado recibido; no verifica cada producto individual. No permite reconstruir el primer despacho, la curva histórica de despachos parciales, la entrega al cliente, OTIF de entrega ni tiempos por cada movimiento. Tampoco tiene valores monetarios ni precios para calcular facturación pendiente en USD.

Las fechas del archivo actualizado ya permiten medir tiempos distintos de cero. La precisión es de días, porque el último despacho no incluye hora. Si la operación cuenta desde liberación o autorización, debe enviarse esa fecha en la API antes de cambiar el inicio del SLA.
