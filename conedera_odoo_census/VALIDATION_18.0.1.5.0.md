# Validación estática — 18.0.1.5.0

Validaciones ejecutadas antes del empaquetado:

- Manifiesto parseado y versión 18.0.1.5.0.
- Todos los Python compilan.
- Todos los XML parsean.
- JavaScript pasa `node --check`.
- Assets de cámara y GPS incluidos en `web.assets_backend`.
- La foto de visita usa widget `camera_capture` sobre un `fields.Image` existente.
- El resumen SQL de productos consolida mediante `commercial_partner_id`.
- La bitácora SQL consolida cotizaciones/visitas por cliente comercial.
- El resumen mantiene orden `quoted_qty desc` y el historial `order_date desc`.
- Reglas de lectura de bitácora/productos ya no dependen de `partner_id.user_id` ni de `user_id` del movimiento.
- Regla de escritura de visitas de vendedor permanece limitada a sus propias visitas.
- Migraciones 18.0.1.5.0 incluyen data guard PRE y POST.
- No se introducen `DELETE`, `TRUNCATE` ni `DROP TABLE` en las migraciones 18.0.1.5.0.
- La búsqueda de RUC/cédula normaliza contactos hijos al cliente comercial principal.

Limitación: no se dispone en este entorno de un runtime completo Odoo 18 + PostgreSQL para ejecutar el upgrade real. Debe validarse con `-u conedera_odoo_census` en una base de prueba/backup antes de producción.
