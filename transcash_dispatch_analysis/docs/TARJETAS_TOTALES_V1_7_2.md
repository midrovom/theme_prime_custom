# Tarjetas y cuadre del pendiente — 1.7.2

## Mismo total en las tarjetas y los plazos

Las tarjetas superiores incluyen Toneladas por despachar y Pallets por despachar. Usan el saldo positivo de las facturas únicas del mismo período, ciudades, modalidades, bodegas y corte seleccionados. Abrir esas tarjetas lleva a las facturas pendientes con esos filtros.

El desglose por acuerdo añade pallets y la fila **Total por despachar**. El total usa los mismos valores canónicos del KPI; la suma de los grupos se valida contra ellos. Incluye tanto Sin plazo como las facturas Por revisar: su falta de evaluación SLA no elimina su carga pendiente. Si faltan pallets, se conserva Sin dato o Parcial en lugar de inventar un cero conocido.

Los acuerdos representan el plazo aplicado a cada factura, no días restantes para el vencimiento. En plazo, Vencidas y Por revisar son conteos de facturas, cuya suma da el total pendiente del grupo. Las columnas de carga identifican toneladas y pallets por separado.

## Diferencias de redondeo

Los grupos y el total se muestran con dos decimales. La suma de grupos ya redondeados puede diferir del total redondeado. Por ejemplo, en el archivo completo:

| Dato | Toneladas mostradas |
| --- | ---: |
| Acuerdo de 3 días | 141,15 |
| Acuerdo de 9 días | 889,47 |
| Redondeo de las filas | −0,01 |
| Total por despachar | 1.030,61 |

El total real es 1.030,61176 t. No se cambian los kilos ni se rebaja artificialmente un grupo para que cuadre. La fila de redondeo aparece solo cuando se necesita; se aplica el mismo criterio a pallets. Las dos tarjetas y el total del cuadro siempre usan el mismo valor y formato.

## Comparar con el plan de vehículos

El resumen y los plazos usan todas las modalidades seleccionadas arriba. El plan de contratación comienza en Solo Entrega Transcash. Por tanto, sus toneladas no tienen que ser iguales mientras los alcances sean distintos.

Ahora el plan muestra explícitamente:

- Resumen y plazos: total de las tarjetas.
- En este plan: peso de los pendientes incluidos en la propuesta de vehículos.
- Otras modalidades: saldo excluido por el alcance Solo Entrega Transcash.
- Diferencia de detalle, si existe: peso de cabecera que no coincide con el detalle asignado. Se muestra aparte y no se hace pasar por exclusión de modalidad.
- Redondeo, cuando las cifras mostradas lo necesiten.

El botón **Planificar todas las modalidades del resumen** cambia solo el alcance del plan para incluir las modalidades ya filtradas y conserva las fechas. No modifica automáticamente los acuerdos, bodegas ni pesos. También se puede filtrar Modalidad = Entrega Transcash arriba para que todos los cuadros analicen exclusivamente ese tipo de entrega.

Ejemplo del archivo recibido en 30/09/2026–29/10/2026, con todas las modalidades: resumen de 871,63914 t = 620,42012 t de Entrega Transcash + 251,21902 t de otras modalidades. No es una consulta del servidor del cliente; sus fechas, modalidades o reglas pueden ser diferentes.

## Pastel por toneladas

El pastel por toneladas sigue usando solo facturas con pesos comparables y conciliados, sin ajustes. Cuando esa base es parcial, su nota identifica el total pendiente de todos los filtros en las tarjetas y plazos. No se fuerza un porcentaje con una base facturada incompleta. El modo Facturas conserva el conteo completo de pendientes del período.

## Actualización

Reemplazar la carpeta del módulo, reiniciar Odoo, actualizar desde Aplicaciones y recargar con Ctrl+F5. No volver a subir el Excel. Se mantiene la corrección 1.7.1: las bases que ya completaron 1.6 o posterior no reconstruyen todo el histórico al actualizar. Esta versión añade cálculos de presentación sobre la consulta del tablero; no añade campos almacenados ni procesos masivos de conversión.
