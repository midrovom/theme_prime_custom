# Estadísticas mensuales · 18.0.1.8.9

Se conserva la persistencia de filtros de 18.0.1.8.8. Se añaden dos gráficos fijos al tablero, sin modificar las configuraciones de tableros personales ni los datos importados.

- Año: fecha Hasta; si no existe, Desde; si ambas están vacías, año del corte histórico seleccionado o año actual. Los gráficos siempre muestran enero–diciembre, independientemente del rango parcial aplicado al resto del tablero. Fuente, corte, ciudad, modalidad, empresas y bodegas se respetan.
- Despachos realizados: facturas únicas con despacho físico completo, agrupadas por fecha efectiva de finalización (incluye facturas emitidas antes del año que completaron su despacho en el año). No equivale a viajes o despachos parciales. Se usan fechas válidas hasta el corte.
- % de retraso: demorados / despachos completos evaluables × 100, con la misma definición de puntualidad del tablero. Sin SLA o con datos inválidos no se incluyen en el porcentaje. Si no hay base evaluable, no se dibuja un cero ficticio.
- Pendientes: facturas del año que siguen con saldo pendiente al corte, agrupadas por mes de factura. El acumulado de cada mes es la suma de los pendientes desde enero hasta dicho mes. Ejemplo: enero 5, febrero 3, marzo 2 → acumulados 5, 8, 10. Si se completa una factura y se actualiza el corte, deja de contarse. No reconstruye saldos históricos de cada cierre ni arrastra facturas de años anteriores. Los meses sin nuevos pendientes conservan el acumulado anterior.
- Con bodegas, se recalcula la factura en función de las líneas seleccionadas, una sola vez por factura. No se duplica por bodega.
- Se conserva el límite de 200.000 facturas del tablero: si el alcance anual lo supera, se informa en los gráficos sin impedir consultar los demás indicadores. No se requieren campos nuevos ni migraciones de datos.

Validación local: 279 pruebas standalone (274 previas y 5 nuevas), sintaxis Python/JS y XML. No se ejecutó una instancia real de Odoo/PostgreSQL ni compilación SCSS porque no están disponibles en el entorno de pruebas. Verificar la navegación y presentación visual en Odoo 18 tras actualizar el módulo.
