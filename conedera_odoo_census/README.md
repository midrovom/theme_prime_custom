# Conedera - Catastro Comercial para Odoo 18 Community

Módulo de campo orientado a móviles para registrar clientes, múltiples tipos de negocio, horarios estructurados, ubicación GPS, visitas comerciales y proformas estándar de Odoo.

## Principios

- `res.partner` sigue siendo la única ficha maestra del cliente.
- `sale.order` sigue siendo la cotización/proforma estándar.
- El Catastro tiene una vista propia para evitar ruido visual y dependencias con campos de terceros.
- Las visitas se almacenan en `conedera.census.visit` para preservar historial y GPS.
- No requiere Enterprise.

## Versión

18.0.1.1.0
