# 18.0.1.4.94 — Consumido y disponible sin redondeo intermedio

- Los importes de gastos reales ya no usan `fields.Monetary`, porque la moneda de Odoo redondeaba al ingresar o actualizar el valor. Ahora usan `fields.Float` sin precisión máxima, con solo un mínimo visual definido por la precisión del presupuesto.
- `actual_amount`, `manual_actual_amount` y `variance_amount` guardan importes con toda la precisión provista por los movimientos; la proyección conserva su prorrateo exacto y sus 2/4/6/8 decimales configurables.
- Las sumas y restas se realizan mediante `Decimal(str(value))` para evitar errores binarios acumulativos.
- Dashboard y PDF no redondean sus datos a dos decimales. Los informes muestran como mínimo la precisión seleccionada, pero también los decimales adicionales si los hay.
- Los movimientos históricos que ya se almacenaron redondeados a la precisión de moneda NO pueden recuperar sus decimales originales por sí solos; se requiere volver a sincronizar el ERP, conservando sus claves externas.
- La huella de movimientos sin identificador se mantiene igual por compatibilidad con histórico y para no provocar registros duplicados.
