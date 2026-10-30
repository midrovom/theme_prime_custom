# Panorama inicial y acuerdos de entrega 1.7

## Presentación

La barra superior conserva a la vista las fechas, bodegas múltiples, favorito y Aplicar. **Más filtros** despliega fuente, corte, ciudad y modalidad. **Opciones** permite guardar vistas, elegir Últimos 30 días o Todas las fechas, abrir el análisis nativo y validar duplicados. El resumen muestra el período, ciudad/modalidad aplicados y la fecha de corte para mantener visible el alcance aunque el panel adicional esté cerrado.

Al entrar se ven los indicadores generales, el pastel y la tabla de plazos antes del detalle de contratación. Las fechas siguen iniciando con los últimos 30 días y se conservan al cambiar de favorito o tablero. Cambiar el tipo de pastel tampoco modifica filtros ni consulta otra población.

## Pendientes por plazo acordado

El acuerdo se toma de `sla_days` y `sla_day_type` ya calculados en cada factura o su alcance de bodegas seleccionado. Se admiten los días configurados, no solo 3 y 9. Los calendarios hábil y calendario se presentan separados aunque tengan el mismo número. Las facturas sin regla forman Sin plazo. Los renglones incluyen ciudades y modalidades desplegables.

| Columna | Definición |
| --- | --- |
| Facturas pendientes | Una factura única que todavía tiene saldo en el alcance aplicado. Incluye parciales. |
| Pendiente (t) | Peso pendiente positivo conocido dividido para 1.000. |
| En plazo | Pendientes evaluables con SLA abierto o que vence al corte. |
| Vencidas | Pendientes evaluables cuyo límite ya pasó al corte. |
| Por revisar | Pendientes no evaluables, con ajustes o sin regla. Se conservan en el total. |

En plazo + vencidas + por revisar = pendientes del grupo. La suma de grupos coincide con el KPI de pendientes y sus toneladas. El conteo enlaza a las facturas exactas del grupo y mantiene fechas, compañías y bodegas; usa los IDs del mismo conjunto calculado, incluso cuando se evalúa solo una parte de una factura por bodega.

**Vencen hoy** usa la fecha de corte de cada factura. **Próximos 3 días** incluye límites entre uno y tres días calendario posteriores a ese corte; no incluye hoy ni atrasos. Son vencimientos próximos, distintos del acuerdo de entrega de 3 días contado desde la factura. Las fechas límite ya incorporan el calendario y feriados de la regla original. Una carga antigua sigue mostrando su estado al corte y mantiene su alerta de antigüedad.

## Pastel facturado y pendiente

Facturado incluye lo pendiente. Dibujar dos sectores con total facturado y total pendiente sumaría dos veces ese saldo. Por eso el pastel parte de una base facturada del 100% y divide esa base en estados que no se solapan.

| Medición | Partes del pastel | Base del 100% |
| --- | --- | --- |
| Facturas, inicial | Sin pendiente / Con pendiente | Todas las facturas únicas de los filtros. Una factura parcialmente despachada sigue Con pendiente. Sin pendiente puede incluir cierres con ajustes; no se etiqueta como prueba de entrega física completa. |
| Toneladas | Despachado / Pendiente | Facturas completas en medición de peso: facturado, despachado y pendiente conocidos, sin ajustes ni observaciones de calidad, y pesos conciliados. |

Ejemplo en toneladas: 100 t facturadas comparables, 80 t despachadas y 20 t pendientes producen 80% / 20%. No se calcula 100 / 120 ni 20 / 120.

La base de toneladas excluye facturas con cualquier peso no disponible, pendientes positivos sin peso válido incluso si otra bodega sí tiene peso, ajustes/devoluciones u observaciones de calidad. También excluye pesos negativos/no finitos o que no concilien con una tolerancia de 0,01 kg por factura. El denominador dibujado es despachado + pendiente conciliados; el peso facturado informado solo puede diferir dentro de esa tolerancia. Se muestra **Base parcial** y el número de facturas comparables respecto del total cuando hay exclusiones. Esas facturas siguen incluidas en los KPI generales, la planificación y los grupos de SLA que correspondan. No se compara un subtotal facturado incompleto con el despacho de todas las facturas para fabricar un porcentaje.

Sin población o sin pesos comparables se indica falta de base y no se dibujan porcentajes artificiales. Por diseño no se mezclan cantidades heterogéneas ni se inventa el peso de una factura desde unidades de productos agregados.

## Actualizar

Reemplazar la carpeta `transcash_dispatch_analysis`, reiniciar Odoo, actualizar el módulo desde Aplicaciones y recargar con Ctrl+F5. No volver a importar el Excel. No se cambia la clave TipoFactura + NumeroFactura ni la publicación de registros vigentes únicos; las nuevas medidas se calculan sobre los datos ya guardados.

Los controles locales y la validación pendiente en la base de destino se detallan en VALIDACION.md.
