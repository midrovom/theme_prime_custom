# v18.0.1.4.96 — Disponible neto sin redondeos intermedios

- El campo visible **Disponible** muestra el saldo **con signo** de cada línea y
  del presupuesto: `Proyectado − Consumido` (usando `Decimal(str(...))`).
- El total ya NO suma únicamente los disponibles positivos. Una línea sobregirada
  resta del total correctamente.
- El campo Exceso y el porcentaje de ejecución se mantienen calculados para
  compatibilidad, pero se ocultan en las vistas de Presupuesto, Proyecciones,
  Proyectado vs. Real, pivote/gráfico y PDFs.
- En el PDF anual quedan tres columnas: Proyectado, Consumido y Disponible.
  En el PDF mensual cada mes tiene esas mismas tres columnas; se conservan los
  saldos de apertura/corte/acumulados del reporte existente.
- Los PDFs usan el formateador que **no corta decimales del consumo ni del saldo**.
  Se muestra como mínimo la precisión elegida y los adicionales si existen.
- No se modifican datos importados del ERP, ni proyecciones ni asociaciones.
  La migración solo recalcula `available_to_spend` almacenado en líneas/cabeceras.
- El presupuesto anual distribuido sigue sujeto a la precisión seleccionada en
  Configuración (2, 4, 6 u 8). Esa precisión es una decisión de captura, no una
  resta redondeada.

Ejemplo: Proyectado 7.800,00 – Consumido 4.122,74 = Disponible 3.677,26.
