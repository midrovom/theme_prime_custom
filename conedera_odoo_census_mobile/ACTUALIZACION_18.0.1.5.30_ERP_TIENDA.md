# Catastro PWA 18.0.1.5.30 — Código de empresa alternativo para ERP

- En Catastro → Configuración → Configurar Consumidor Final, seleccionar la empresa y definir **Código de empresa ERP para Tienda** (texto con ceros iniciales).
- Las proformas nuevas creadas desde Gestión de Tienda quedan marcadas `catastro_pwa_retail_origin=True`.
- Las proformas de Campo y las creadas directamente en Odoo **no** quedan marcadas.
- Instalar además `catastro_pwa_retail_radis_bridge` para transformar `order_company_code` antes de enviar a `check_update_qoutes` (botón y cron). El puente original `stock_api_assing` no cambia.
- Las proformas de Tienda creadas **antes** de la 1.5.30 no se reclasifican automáticamente. Revisarlas antes de migrar su código ERP.
- Para Tienda sin código ERP definido, el puente bloquea el envío; no usa silenciosamente el código normal.
- Sin cambios en company_id real, credenciales de la API, precios, descuentos, Loyalty, Radis ni cola offline.
