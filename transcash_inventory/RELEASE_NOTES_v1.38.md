# v1.38 — Consultas por agrupaciones naturales sobre Odoo

- La IA recibe el esquema físico autorizado de productos, ventas, compras y stock de la compañía activa.
- Planificación estructurada en una sola petición OpenAI; el servidor compila el SQL SELECT seguro, sin SQL libre del modelo.
- Agrupación por formato, marca, categoría, proveedor del catálogo, o combinaciones de hasta cuatro campos.
- La intención literal del usuario es vinculante: «stock en unidades agrupado por formato» usa `group_by=formato`, `metric=stock_unidades`, sin filtrar un formato específico.
- Consultas agrupadas sin TOP explícito incluyen todos los grupos hasta un techo de 3.000. Las salidas no muestran SQL ni trazas; la bitácora administrativa sí.
- El stock es al último corte; se advierte que m², unidades, cajas y piezas no deben sumar como unidades homogéneas.
- Respeta `company_id` y `snapshot_id` en todas las consultas; preserva exportación Excel y los endpoints API.
- No ofrece SQL libre ni acceso a tablas fuera del catálogo autorizado; las peticiones no soportadas indican qué dato falta.
