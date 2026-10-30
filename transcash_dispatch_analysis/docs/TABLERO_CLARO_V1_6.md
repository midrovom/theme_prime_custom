# Tablero y planificación 1.6

## Por qué podían aparecer tres vehículos para 27,95 t

La versión anterior calculaba cada combinación de compañía, fuente, bodega y destino como una salida independiente. Su resumen de ciudad sumaba esos vehículos. La misma ciudad podía tener un tráiler para una bodega y camiones pequeños para otras. El total de la ciudad no se cargaba automáticamente en un único vehículo.

Ahora la fila identifica cuántas bodegas y grupos de salida hay. **Ver cálculo y carga por bodega** muestra el peso de cada origen, la capacidad útil, los viajes, los vehículos, los disponibles, la contratación y los días. La revisión muestra la causa concreta de una estimación parcial.

El selector **¿Puedes juntar la carga de varias bodegas?** permite comparar:

| Opción | Cómo calcula |
| --- | --- |
| No: una salida por cada bodega | Conserva las salidas y vehículos independientes. Es el valor inicial para respetar los orígenes existentes. |
| Sí: agrupar para el mismo destino | Suma el pendiente de las bodegas de una misma compañía, fuente y ciudad. Aplica la regla de ciudad y una sola asignación de vehículos disponibles a ese grupo. |

Agrupar supone que la carga puede recogerse o reunirse y que el ciclo de viaje configurado incluye las recogidas. No programa rutas geográficas. Una regla de transporte específica de una bodega impide agrupar los orígenes de ese destino, para conservar sus restricciones; el detalle lo explica. No se mezclan compañías ni fuentes. Faltantes de origen o ciudad siguen separados y por revisar.

Ejemplo ilustrativo, no verificación de la fila instalada del cliente: 27,95 t agrupadas, tráiler de 28 t con 90% de uso, plazo de 3 días y un viaje por vehículo al día. Carga útil: 25,2 t. Se necesitan 2 viajes. Un tráiler reutilizado termina en 2 días. Si el plazo fuera un solo día, se necesitarían 2 vehículos para hacer esos viajes en paralelo. No se propone cargar 27,95 t en un viaje de 25,2 t útiles.

## Cómo leer los números

| Dato | Significado |
| --- | --- |
| Vehículos necesarios | Cantidad asignada a ese grupo para terminar dentro del plazo. Un vehículo puede hacer varios viajes. |
| Por contratar | Máximo entre necesarios menos disponibles y cero, calculado para cada grupo. |
| Viajes totales | Número de cargas/salidas completas, incluido el ciclo de regreso configurado. |
| Días para terminar | Días de trabajo con los vehículos necesarios calculados. Los grupos trabajan en paralelo. |
| Con los disponibles | Estimación separada, visible en el desglose. Sin vehículos disponibles no tiene medición. |
| Parcial | Hay peso desconocido, datos por revisar o capacidad sin configurar. El detalle muestra la causa. |

Los vehículos disponibles iniciales son supuestos, no una consulta del inventario real. Pon 0 si todos deben contratarse. La prioridad de selección sigue siendo menos vehículos dentro del plazo, después menos viajes y después menos capacidad sobrante. No estima tarifas. Los pallets se muestran como carga informada, pero no se usan como capacidad de vehículo: faltan posiciones/volumen y restricciones de cada equipo.

## Fechas y botones

- Primera carga: hoy menos 29 días hasta hoy, ambos incluidos; usa `fields.Date.context_today` y la zona del usuario de Odoo.
- Los filtros se obtienen antes de la primera consulta de datos. Todos los cuadros comparten ese rango por fecha de factura; el estado se evalúa al corte importado.
- **Últimos 30 días** aplica de nuevo ese período; **Todas las fechas** quita ambos límites.
- Los botones de indicadores y análisis dinámico usan los filtros de los resultados que están en pantalla. Cambios de filtros pendientes de aplicar no cambian el detalle de cifras ya mostradas.
- Desde 1.6.1, cargar un favorito desde el tablero aplica sus otros filtros y la agrupación guardada, conservando las fechas seleccionadas en pantalla. También conserva Todas las fechas y los rangos con un solo límite. Cambiar de tablero conserva igualmente las fechas. El período cambia cuando editas Desde/Hasta o pulsas los botones de fechas.
- Las acciones programáticas de facturas, histórico y recálculo múltiple incluyen `views`, además de `view_mode`. Esto corrige la lectura de `map` sobre una lista ausente. Referencia: https://www.odoo.com/documentation/18.0/developer/reference/backend/actions.html#window-actions-ir-actions-act-window

## Toneladas y pallets

La sección Carga del período muestra toneladas facturadas, despachadas y pendientes; pallets facturados y pendientes. La tabla de carga por destino muestra las mismas medidas sobre todos los filtros superiores. El plan de transporte usa únicamente pendientes, y por defecto solo Entrega Transcash.

El Excel recibido contiene PalletsPendientes en sus 54.392 renglones y no contiene PalletsFacturados. No es correcto multiplicar los pallets pendientes por una razón de cantidades: los renglones consolidados mezclan productos. Por eso Pallets facturados aparece **Sin dato** hasta recibir ese campo opcional. Un cero informado se conserva como cero conocido. Valores negativos se marcan no disponibles. Los valores parciales suman únicamente la parte informada. En las listas nativas se incluye la disponibilidad para interpretar los subtotales conocidos.

El peso facturado sigue requiriendo PesoFacturado o la conciliación de pesos sin ajustes desconocidos. Se distingue su subtotal parcial de un total completo. Se conservan la llave TipoFactura + NumeroFactura, el índice de vigentes únicos, los históricos y el selector de bodegas múltiples.

## Actualizar

1. Reemplazar la carpeta `transcash_dispatch_analysis` con esta versión, manteniendo el nombre técnico.
2. Reiniciar Odoo y actualizar el módulo desde Aplicaciones.
3. Recargar el navegador con Ctrl+F5 y entrar de nuevo al tablero.

No subir otra vez el Excel. La actualización recupera los pallets informados de los registros originales guardados. Las capacidades, reglas, fuentes y datos importados se conservan. Las comprobaciones realizadas y las pendientes de ejecutar en Odoo están en VALIDACION.md.
