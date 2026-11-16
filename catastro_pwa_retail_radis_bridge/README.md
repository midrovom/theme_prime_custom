# Puente ERP Tienda → Radis (Odoo 18)

## Instalar

1. Actualizar `conedera_odoo_census_mobile` a 18.0.1.5.30.
2. Instalar `catastro_pwa_retail_radis_bridge` (depende de `stock_api_assing`, NO lo modifica).
3. En **Catastro → Configuración → Configurar Consumidor Final** seleccionar compañía y establecer código ERP especial para Tienda, por ejemplo `T001`. Se mantiene el código ERP normal de `res.company.company_registry`.
4. Crear una proforma NUEVA desde Gestión de Tienda PWA y enviar un ejemplo a Radis; comprobar `order_company_code`.

## Comportamiento

- Solo se sustituye `order_company_code` cuando `sale.order.catastro_pwa_retail_origin` y `catastro_pwa_origin` son verdaderos.
- Cotizaciones Campo o creadas en Odoo conservan su `order_company_code` original.
- Se aplica al envío manual y al cron porque ambos llaman `api.administrator.call_api`.
- Se conserva el `company_id` real para las credenciales y el destino de la API.
- Sin código configurado, se detiene el envío para evitar clasificar una venta de Tienda como venta normal.
- El cambio no modifica porcentajes `discount_percent`, `increase_percent`, `price_unit`, `order_payment_code`, ni comentarios.
- Combina mediante `super()` con el puente existente `catastro_radis_percentage_bridge` si está instalado.
- Proformas anteriores a la marca nueva no se migran automáticamente.

**IMPORTANTE:** Radis debe confirmar que el código alternativo esté configurado en su catálogo de empresas.
