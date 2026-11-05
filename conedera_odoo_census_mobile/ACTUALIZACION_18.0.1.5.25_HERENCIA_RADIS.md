# Catastro PWA 18.0.1.5.25 — envío Radis mediante módulo heredado

El módulo base `stock_api_assing` se conserva SIN MODIFICACIONES.
Para enviar `discount_percent` e `increase_percent` desde el botón de la PWA y el cron,
instale el módulo separado `catastro_radis_percentage_bridge`.

- El puente hereda `api.administrator.call_api` y solo intercepta `POST check_update_qoutes`.
- No reimplementa autenticación, HTTP ni cambio de estado de Radis.
- La PWA utiliza `sale.order.action_export_to_radis()` del módulo original.
- Sin puente se bloquean desde la PWA las cotizaciones con descuento o incremento,
  para evitar que los porcentajes se pierdan en la integración.
- La PWA no cambia el esquema de IndexedDB ni los datos offline.

Actualización recomendada: primero PWA 18.0.1.5.25, después instalar
`catastro_radis_percentage_bridge` 18.0.1.0.0 y reiniciar Odoo.
Validar las dos claves nuevas con el receptor Radis antes de producción.
