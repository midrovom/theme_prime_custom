# Puntualidad y mayores retrasos · 18.0.1.8.7

La sección aparece inmediatamente después del panorama superior y antes de los pendientes por plazo. Usa las mismas facturas únicas y los mismos filtros aplicados del tablero. No requiere otra importación.

## Pastel: despachos a tiempo y demorados

La unidad es **una factura completada**, no cada salida de un camión ni cada despacho parcial. El origen es un corte acumulado por factura/detalle; no proporciona un historial de eventos individuales.

| Parte | Qué incluye |
| --- | --- |
| A tiempo | Facturas físicamente completadas hasta su fecha límite, inclusive |
| Demorados | Facturas físicamente completadas después de su fecha límite |
| 100% | Suma de las dos partes: facturas completadas con plazo y datos evaluables |
| Fuera del pastel | Pendientes y completadas sin medición; se muestran sus cantidades |

Se excluyen ajustes/devoluciones, datos inválidos, ausencia de plazo o fechas inconsistentes. Sin base evaluable se muestra **Sin medición**, en lugar de un 0% artificial. Los botones de la leyenda abren el conjunto exacto medido.

Este porcentaje corresponde a despachos completados; la tarjeta existente **Cumplimiento del período** también incluye pendientes vencidas exigibles en su denominador. Por ello son mediciones diferentes y no tienen que dar el mismo porcentaje.

## Mayores retrasos

Se puede elegir **Despachados demorados** o **Pendientes vencidos**. El cambio es local, sin RPC ni modificación de filtros. Cada vista muestra:

- Cantidad de facturas con retraso medible en esa cohorte.
- Promedio del atraso de todas esas facturas, aunque solo se vean cinco filas.
- Mayor atraso de la cohorte.
- Facturas ordenadas de mayor a menor atraso, con destino, fecha límite, fecha de despacho/corte y días. Cinco al inicio, ampliables hasta diez; **Ver todas** abre la lista nativa del conjunto completo. La lista nativa conserva su orden habitual; el ranking por días está en el tablero.

El atraso se mide en **días calendario después de la fecha límite**:

- Despachados demorados: fecha de finalización del despacho menos fecha límite.
- Pendientes vencidos: fecha del corte de esa factura menos fecha límite.

La fecha límite proviene del SLA aplicado, con sus días hábiles o calendario y feriados. Se utiliza una unidad calendario para comparar magnitudes; el campo histórico `late_days` conserva su unidad SLA original. Ejemplo: límite 6 de enero y despacho 12 de enero equivalen a 6 días calendario de atraso.

El rango sigue siendo de **fecha de factura**, tal como el resto del tablero. El pendiente se evalúa al corte almacenado, no usando la fecha de hoy sobre un corte antiguo. Al seleccionar varias bodegas, se recalcula el estado de sus líneas y cada factura se cuenta una vez; una factura puede estar completada en las bodegas seleccionadas y pendiente en otras.

## Actualizar

1. Respaldar la instalación siguiendo el procedimiento habitual del servidor.
2. Reemplazar la carpeta completa `transcash_dispatch_analysis` y reiniciar todos los trabajadores de Odoo.
3. Actualizar el módulo y confirmar **18.0.1.8.7**.
4. Recargar el navegador con **Ctrl+F5** y abrir el tablero.

No agrega campos, modifica facturas, lanza una sincronización ni reconstruye cortes históricos. Los cron, tamaños adaptativos, cursores de importación, publicación del corte y validación de fechas conservan el código de 1.8.6.

## Validación

Los controles automáticos y sus límites se documentan en `VALIDACION.md`. Las pruebas funcionales locales usan el cálculo real y un ORM simulado; las pruebas de navegador usan OWL real y datos sintéticos. Las pruebas nativas adicionales se incluyen para ejecutar en un Odoo/PostgreSQL de pruebas; no se ejecutaron contra la base del usuario. Esta entrega no está instalada en su servidor.
