# Transcash Logística V5.0

El módulo V5 contiene un nuevo modelo de **embarque** que agrupa guías, controla una factura de proveedor por embarque y conserva la recepción, evidencias y daños por guía.

**Manual completo:** `ACTUALIZACION_V5.md`. Actualice el módulo sobre V4.2; no desinstale.

WebApp: `/transcash/embarques` para chofer y empresa transportista; `/transcash/guias` para las guías.


## V5.6 Liquidaciones independientes

Jefe de Logística negocia y aprueba embarques; transportistas presentan liquidaciones agrupadas en `/transcash/proveedor` y adjuntan sus facturas externas; Contabilidad verifica y registra pagos manualmente desde **Liquidaciones y pagos**. No se crean asientos ni facturas del módulo Contabilidad. Guía: `TRANSCASH_V56_LIQUIDACIONES_Y_PAGOS.md` fuera del ZIP.


## V5.7 — Aprobación con novedades y KPIs

La aprobación excepcional de fletes está limitada al Jefe de Logística con grupo adicional.
Requiere que todas las guías hayan sido cerradas por chofer y una justificación auditable;
no cierra incidentes ni sustituye la revisión de facturas por Contabilidad.

El menú independiente «Transcash · Indicadores» usa el permiso «Analítica: consultar dashboard logístico».
Los filtros de fecha y frecuencia permiten examinar viajes, destinos, peso, daños, marcas,
proveedores de productos, transportistas y choferes.

Para el contrato JSON actualizado consulte `TRANSCASH_V57_API_EJEMPLO.json` y
`TRANSCASH_V57_GUIA_INSTALACION_DASHBOARD_API.md` distribuidos junto al ZIP.
