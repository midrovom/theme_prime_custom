# Saldo disponible no negativo y exceso de gasto — 18.0.1.4.95

- La diferencia **interna** `variance_amount` mantiene signo, precisión original y sus saldos acumulados para no alterar las fórmulas de los cortes históricos.
- `available_to_spend = max(proyectado - consumido, 0)` y `excess_amount = max(consumido - proyectado, 0)` son nuevos indicadores almacenados, calculados por línea.
- Las sumas en presupuestos, lista, tabla dinámica y PDFs agregan disponible positivo y exceso por separado (no compensan un exceso de agua con el saldo disponible de electricidad).
- El saldo neto matemático se conserva: `disponible - exceso = proyectado - consumido`. Los reportes mensuales mantienen el saldo de arrastre **firmado** para los períodos posteriores, aunque presentan el saldo disponible negativo como cero.
- En la migración se recalculan únicamente los campos nuevos en las solicitudes ya existentes, incluidas las aprobadas, sin modificar presupuestos ni movimientos de consumo.
