# Catastro PWA 18.0.1.5.26 — Código ERP de la forma de pago

- Se añade `erp_code` (Char, conserva ceros) al maestro `catastro.quote.payment.option`.
- Visible en formulario y lista de Condiciones de pago PWA, en Configuración de Catastro.
- El código puede estar vacío en registros históricos; se exige al exportar una proforma que utilice esa condición.
- No se alteran los precios, porcentajes de recargo, descuentos Loyalty, ni la presentación para el vendedor.
- Para enviar el valor a la cabecera de la API Radis, instalar/actualizar aparte `catastro_radis_percentage_bridge` a 18.0.1.0.1.
- La clave de cabecera es `order_payment_code` y se agrega a los payloads manuales y cron.
- El módulo original `stock_api_assing` NO se edita.
- Confirmar que el receptor de Radis admite la nueva clave de cabecera antes de producción.
