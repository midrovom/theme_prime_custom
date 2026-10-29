# Análisis de despachos actualizado

**Fuente:** Analisis Despachos Trasncash(1).xlsx. Se usa exclusivamente el último archivo recibido.

**Corte utilizado:** 29/10/2026, coincidente con la fecha más reciente de factura y despacho. Confirmar que es también la fecha de extracción del exportador al cargarlo en Odoo.

## Resultados

| Indicador | Todas las modalidades | Entrega Transcash |
| --- | ---: | ---: |
| Facturas distintas | 44.989 | 1.727 |
| Facturas pendientes | 383 | 100 |
| Pendientes con despacho parcial | 147 | 30 |
| Pendientes sin despacho físico registrado | 236 | 70 |
| Cierres con tiempo medible | 43.631 | 1.225 |
| Tiempo promedio, días calendario | 1,65 | 9,28 |
| Mediana, días calendario | 0,0 | 5,0 |
| P90, días calendario | 4,0 | 22,0 |
| Peso pendiente, kg | 1.030.611,76 | 767.229,77 |
| Cajas pendientes | 36.527,94 | 26.408,15 |
| Pallets pendientes | 830,78 | 636,60 |
| Pendientes con antigüedad mayor a 30 días | 100 | 44 |
| Antigüedad promedio de pendientes, días | 37,85 | 61,87 |
| Antigüedad máxima de pendientes, días | 294 | 273 |
| Cumplimiento oficial por plazo | Sin medición | Sin medición |

El promedio usa únicamente cierres físicos medibles, sin ajustes/devoluciones ni observaciones de calidad. El P90 de 22 días para Entrega Transcash significa que el 90% de sus 1.225 cierres medibles se realizó dentro de ese tiempo, según las fechas registradas. No es un plazo recomendado ni un compromiso de servicio.

## Lectura operativa

Entrega Transcash concentra 74,44% del peso pendiente, con 26,11% de las facturas pendientes. Conviene priorizar por peso, ciudad y antigüedad, además del número de facturas.

El promedio general mezcla retiros de clientes, otros transportistas y entregas. Para evaluar la operación de Transcash, usar su modalidad y mostrar el resto como comparación separada. La mediana de 5 días frente al promedio de 9,28 muestra que existen cierres largos que elevan el promedio.

La antigüedad mide tiempo desde la factura, no atraso contractual. No se puede clasificar una factura como vencida sin definir el plazo y el inicio del reloj. También deben distinguirse esperas por autorización, programación del cliente u otros motivos si la operación los maneja.

## Ciudades de Entrega Transcash con más peso pendiente

| Ciudad | Pendientes | Peso pendiente, kg | Cierres medibles | Promedio, días | P90, días |
| --- | ---: | ---: | ---: | ---: | ---: |
| QUITO | 15 | 175.779,36 | 116 | 7,13 | 19,0 |
| GUAYAQUIL | 38 | 94.129,94 | 225 | 10,14 | 31,0 |
| AMBATO | 6 | 83.932,20 | 9 | 16,00 | 24,6 |
| MILAGRO | 2 | 67.058,41 | 63 | 13,62 | 32,2 |
| MANTA | 1 | 55.175,19 | 9 | 8,78 | 18,2 |
| RIOBAMBA | 4 | 40.930,85 | 49 | 6,67 | 16,6 |
| MACHALA | 8 | 31.631,94 | 178 | 10,54 | 26,3 |
| IBARRA | 1 | 31.360,00 | 32 | 11,47 | 22,0 |
| VENTANAS | 1 | 29.148,82 | 11 | 8,18 | 20,0 |
| MACAS | 1 | 26.045,55 | 6 | 8,83 | 21,5 |

Los tiempos de cada ciudad corresponden a cierres medibles; los pendientes y su peso corresponden al saldo al corte. Ciudades con pocos cierres requieren cautela al fijar plazos a partir de su P90.

## Simulación de plazos, no indicador oficial

Para mostrar el efecto del parámetro, esta tabla aplica un mismo plazo hipotético a todas las ciudades de Entrega Transcash, desde la fecha de factura y en días calendario. Estos plazos no están grabados como política real del módulo.

| Plazo supuesto | Pendientes vencidas evaluables | Cumplimiento de despachadas | Cumplimiento exigible |
| --- | ---: | ---: | ---: |
| 2 días | 75 | 34,29% | 32,31% |
| 3 días | 73 | 40,57% | 38,29% |
| 5 días | 73 | 54,12% | 51,08% |
| 7 días | 62 | 66,29% | 63,09% |

Cumplimiento exigible = despachadas evaluables a tiempo / (despachadas evaluables + pendientes vencidas evaluables). Las pendientes aún en plazo no entran en el denominador. Ajustes/devoluciones y registros no evaluables se presentan por separado.

## Calidad y alcance del archivo

- 54.392 registros consolidados por factura/bodega; 44.989 facturas distintas. No contiene SKU.
- 17.743 registros tienen fecha de último despacho distinta de la factura. El problema de tiempos uniformes de la versión anterior ya no aparece.
- No se detectaron duplicados factura/bodega ni diferencias entre facturado, despacho físico, ajustes y pendiente, con tolerancia de 0,000001.
- 81 facturas carecen de ciudad. 150 facturas tienen algún saldo negativo. En conjunto, 231 facturas presentan observaciones de calidad.
- 891 facturas tienen ajustes/devoluciones; son una población separada y puede haber solapamiento con otras observaciones.
- No se detectaron errores de Excel en este archivo.
- Peso interpretado en kg y cajas/pallets como cantidades informadas por el exportador; confirmar las unidades del origen al conectar la API.

El cierre se evalúa al nivel de bodega recibido. No prueba la cobertura individual de cada SKU ni permite deshacer compensaciones que el origen ya haya hecho al consolidar productos. Para ese control, la API debe incluir detalle por SKU.

La última fecha por bodega permite medir el cierre consolidado, pero no el primer despacho, la secuencia de parciales ni la entrega al cliente. No hay importes para medir el saldo pendiente en dólares. Las fechas del último despacho no tienen hora: la precisión de tiempos es de días.

## Módulo entregado

Versión técnica **18.0.1.1.0**, carpeta `transcash_dispatch_analysis`. Incluye tablero, parámetros por ciudad/modalidad, calendarios y feriados, constructor de visuales, análisis dinámico, detalle por bodega o producto, importaciones en segundo plano, cortes históricos, perfiles y API de recepción por bloques. El conector específico a la API origen queda pendiente de su documentación.

El cumplimiento comienza como **Sin medición** hasta configurar y aplicar plazos. Las vencidas no se presentan como cero cuando no hay pendientes evaluables. La vista previa permite simular y guardar opciones en el navegador; el módulo guarda las configuraciones en Odoo.

## Pendiente de definición

1. Alcance del SLA: solo Entrega Transcash, todas las modalidades o reglas distintas por modalidad.
2. Plazos por ciudad, calendario o hábil, feriados e inicio desde facturación o desde liberación/autorización.
3. Documentación de API origen, ejemplo de respuesta, identificadores estables, fecha de extracción y frecuencia de actualización.

## Validación

Se conciliaron los totales del archivo completo, se ejecutaron 39 pruebas del motor de cálculo y se verificó la coincidencia entre vista previa y Python en las 1.727 facturas de Entrega Transcash para un escenario de días hábiles con feriado. Se revisaron sintaxis Python/JavaScript/XML, referencias de campos, manifiesto y permisos declarados.

La instalación, las pruebas ORM/ACL con PostgreSQL y el montaje visual de OWL deben ejecutarse en una base de prueba Odoo 18. No se afirma una instalación en tu servidor ni una conexión activa con el ERP origen.

**Huella SHA-256 del archivo analizado:** `af70ab3e6aa4a7debe7409639c122f4b4b7bd9382cc0b35da4c50f2aa15f587d`.
