# v1.4.70 – Fecha ERP inequívoca y trazas de guardado

- Fecha del ERP `oct  8 2026 12:00:00:000` = **8 de octubre de 2026** = `08/10/2026` (DD/MM/AAAA).
- Fecha en presupuesto `08/09/2026` = **8 de septiembre de 2026**. Es correcto que el consumido sea 0 si no hay gastos de septiembre.
- Proyecciones mensuales muestran una columna **Fecha interpretada** con el mes escrito para evitar confusiones.
- Los presupuestos sin líneas no consultan al ERP. Registros de log `[PRESUPUESTOS GUARDADO]` permiten diagnosticar la duración de validación, ORM y consulta de consumos de los guardados.
- Se cambió `search_count` por `search(limit=1)` para verificar la existencia de un presupuesto pendiente sin contar todos los registros.
- El importe solo se refleja si el movimiento ya existe en Gastos reales o si pudo importarse desde `getconsumosgastos/2`. Si no aparece con la fecha exacta, inspeccionar `Historial API` y logs del servidor.
