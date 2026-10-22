# Transcash Guías API v2.3 · Fechas y vínculos de marca/proveedor

## Causa raíz (confirmada en código de v2.2 y v5.32)
- `tc.guide` almacena `erp_start_date`, `erp_end_date`, `erp_planned_date`, pero `publication.py` v2.2 **no** escribía `fecha_inicio_traslado`, `fecha_fin_traslado`, `fecha_prevista` al crear/actualizar `transcash.guia`.
- Las fichas comerciales se creaban en `tc.guide.line.private` pero la publicación omitía toda relación explícita con `transcash.guia.linea`. El dashboard recurría a combinar cadenas de identificadores, sin garantía de trazabilidad.
- La tarjeta Kanban operativa mostraba únicamente `fecha_prevista` que quedaba sin actualizar.

## Cambios v2.3
1. Copia las tres fechas a **campos existentes** del modelo operativo de Odoo, interpretando la fecha como calendario local (`America/Guayaquil` por defecto) y guardando la marca técnica `00:00` local en UTC. **No representa un evento real**: las fechas ERP no deben confundirse con salida/llegada efectiva de la PWA.
2. Añade fechas tipo `Date`, computadas y no almacenadas, para mostrar los valores originales sin hora y sin efecto de huso horario en Kanban, lista y formulario.
3. Agrega `operational_line_id` a `tc.guide.line.private` (modelo **privado del conector**) y lo enlaza por `(empresa, id_externo, id_linea)` con `transcash.guia.linea`. Ningún nombre de marca/proveedor se copia a campos públicos de guía/línea.
4. Añade pestaña comercial y acción de consulta dentro de la guía operativa, exclusivas del grupo `Administrador de integración guías` o `base.group_system`.
5. La fuente del dashboard único comercial es primero la relación privada `operational_line_id` y, por compatibilidad con históricos aún sin conciliar, la llave `(empresa,id_externo,id_linea)`.
6. KPI comerciales: guías con roturas específicas de esa marca/proveedor, reportes de rotura (sin rechazados), reportes pendientes/aprobados, cantidad transportada en m²/unidades, peso kg, daños en m²/unidades. Incidencias genéricas de una guía no se atribuyen arbitrariamente a todas sus marcas.
7. Reparación histórica **sin importar datos nuevos ni modificar el embarque**: completar fechas (solo las faltantes si ruta/embarque en progreso) y enlazar fichas privadas con las líneas operativas existentes. No se tocan chofer, proveedor de transporte, estados, firmas, roturas ni liquidaciones.

## Instalación
1. Respaldar base PostgreSQL y carpeta `transcash_guias_api`.
2. Reemplazar **solo** `transcash_guias_api` por v2.3. Conservar `logistica_transcash` que está funcionando.
3. Reiniciar Odoo, actualizar `transcash_guias_api` y recargar navegador con Ctrl+F5.
4. Con rol administrador de integración: **Logística Transcash → Operación logística → Reparar fechas y relaciones comerciales** (empresa actual).
5. Verificar guías 32625 y 32629 (u otra del ERP) en **Guías para armar rutas**: `Inicio ERP`, `Fin ERP`, `Prevista ERP` deben mostrar fecha sin hora. En la guía operativa verificar la pestaña privada (solo administrador).
6. En **Inteligencia logística → Marcas / Proveedores de productos**, revisar guías con roturas, reportes, m² y unidades dañados. Cambiar fecha a “Registro en Odoo” y ampliar intervalo si es necesario.
7. Ejecutar consultas **de solo lectura** de `docs/validacion_fechas_marcas_v23.sql` para validar datos en PostgreSQL.

## Limitaciones y precauciones
- No se ejecutaron consultas en la base de datos real. Se validaron Python, XML, JavaScript y un caso de conversiones de fecha con zona Ecuador.
- Si no existe línea operativa con el mismo `external_line_id`, la reparación informa **línea sin coincidencia**; no crea líneas en guías en operación para proteger sus roturas y entregas.
- La sincronización normal publica guías nuevas y actualiza únicamente los campos permitidos por el estado de la operación; la reparación histórica es una acción aparte.
- Ningún nuevo módulo: se mantiene `getguiaslogistica` dentro de `api.administrator` y el dashboard único en `transcash_guias_api`.
