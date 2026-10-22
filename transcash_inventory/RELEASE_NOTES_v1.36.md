# TRANSCASH Inventario Inteligente 18.0.1.36.0

## Consultas de stock con cantidades de compra y venta

- Corrige la ruta de stock directa que antes devolvía columnas fijas y omitía las cantidades solicitadas.
- Detecta las métricas solicitadas en lenguaje natural: `cantidad_comprada`, `cantidad_vendida` y, si se solicitan, meses de última compra y última venta.
- El rango de stock se aplica al inventario físico del último corte (`stock_unidades > 10 AND stock_unidades < 100`).
- Agrega cada movimiento por SKU antes de unir las compras y ventas; evita duplicaciones y mantiene el filtro de la empresa y snapshot activos.
- Las cantidades compradas/vendidas respetan el período seleccionado en el dashboard y también aparecen en la exportación Excel.
- La ruta de importaciones antiguas (snapshot compacto) utiliza las mismas columnas, sin esperar a reconstruir las tablas SQL.
- Se refuerza el contexto de ChatGPT y la validación del plan para impedir que omita columnas de cantidades expresamente solicitadas.
- No modifica los endpoints de API Administrator ni las pantallas o fotografías existentes.

### Ejemplo

`Dame la lista de SKU con stock mayor a 10 y menor a 100, incluyendo descripción, cantidad comprada y cantidad vendida en el período seleccionado.`

**Nota:** las cantidades corresponden a la unidad informada por el ERP para cada SKU; no se convierten automáticamente cajas a m² ni piezas.

### Despliegue

Actualizar sobre el módulo anterior, sin desinstalar ni volver a sincronizar la información. Probar inicialmente en una base de pruebas y validar la consulta sobre el inventario de la empresa activa.
