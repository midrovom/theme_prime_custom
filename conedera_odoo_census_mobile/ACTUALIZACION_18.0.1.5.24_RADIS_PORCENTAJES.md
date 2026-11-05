> Nota histórica: esta guía de 18.0.1.5.24 ha sido reemplazada. Para instalaciones nuevas **NO modifique stock_api_assing**; utilice `catastro_radis_percentage_bridge` y la PWA 18.0.1.5.25.

# Catastro PWA 18.0.1.5.24 — Integración Radis con porcentajes

- Permite enviar cotizaciones con descuentos por línea solo si está instalado `stock_api_assing` con método `_radis_line_percentages_payload_version() >= 2` (versión 18.0.1.2.0 o posterior).
- Si el servidor conserva la integración antigua, se bloquea el envío de cotizaciones con `discount` distinto de cero, con un aviso de actualización claro.
- Conserva el bloqueo de recompensas Loyalty como productos separados (que requieren otro contrato).
- No duplica la llamada de API ni envía peticiones directamente desde el navegador: invoca `sale.order.action_export_to_radis()`.
- Actualiza número de versión de app, API, archivos estáticos y Service Worker para evitar desajustes de caché.
- No modifica el almacenamiento local ni datos offline.

**Orden de actualización:** 1. Respaldar y reemplazar `stock_api_assing`, actualizar módulo. 2. Actualizar `conedera_odoo_census_mobile`. 3. Reiniciar Odoo y PWA. 4. Validar una cotización de prueba con descuento e incremento en Radis. Los dos campos nuevos son `discount_percent` e `increase_percent` y deben ser admitidos por el receptor. **Sin prueba en la API de Radis no se garantiza la interpretación de importes**.
