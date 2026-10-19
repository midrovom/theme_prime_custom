# v1.4.68 — Mejoras del botón Actualizar/Sincronizar API

- Se mantienen los **tres** endpoints GET configurados en `api_administrator` y el cron cada 5 horas.
- **Cuentas y centros**: escritura por bloques de hasta 500 elementos usando `INSERT ... ON CONFLICT DO UPDATE` con condición `WHERE ... IS DISTINCT FROM ...`; si ya está igual no se bloquea/actualiza. Se conserva el rubro asignado a las cuentas y no se borran registros ausentes del ERP. Los códigos históricos con espacios se normalizan con la rutina anterior.
- **Consumos**: se detectan movimientos existentes por `source_key` en bloques, se comparan mediante datos de PostgreSQL y solo se actualizan si tienen cambios. Los nuevos se crean en grupos de 200 mediante ORM de Odoo, manteniendo restricciones y cómputos. Se precargan las proyecciones del año en una consulta y se aplica la prioridad del subcentro exacto sobre la línea genérica.
- **Subcentros**: generación de su catálogo agrupada; no requiere parsear fecha e importe para todos los años del histórico.
- **Contadores y trazabilidad**: el Historial API y la notificación incluyen `tiempo_api` (espera y recepción de la respuesta) y `tiempo_guardado` (procesamiento y escritura en Odoo) por endpoint. El log del servidor muestra el tiempo total por empresa y año.
- No se altera la selección año/mes/centro/subcentro ni los cálculos de Consumido y Disponible.

**Límite**: si la mayor parte del minuto corresponde a la respuesta de `getconsumosgastos/2`, esta versión no puede acelerar por sí sola el servidor ERP; ese endpoint devuelve todos los años y no se ha documentado un parámetro de filtrado. Recomendaciones posteriores basadas en las mediciones: ofrecer filtro de fechas/paginación o entrega incremental desde el ERP, o realizar la sincronización completa en el cron y mostrar datos ya sincronizados en el formulario.

**Pruebas**: comprobación estática local Python/XML y archivo ZIP; las pruebas de Odoo 18 y los tiempos reales de conexión deben verificarse en una instancia de pruebas.
