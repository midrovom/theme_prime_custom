# Catastro PWA 18.0.1.5.15 — comparador de precios con impuestos

## Cambio
Cada tarjeta del catálogo muestra el precio unitario **con impuestos** según la forma de pago elegida y compara las alternativas configuradas para la empresa. El cálculo lo realiza el servidor de Odoo 18 mediante su motor fiscal (impuestos del producto y posición fiscal del cliente), manteniendo el contexto de lista de precios y cantidad.

## Presentación
- Precio final de la forma de pago seleccionada, destacado.
- Hasta tres formas de pago alternativas visibles, con el resto desplegable.
- No se exponen porcentajes ni valores internos del recargo.
- El precio es informativo por unidad, antes de descuentos por Loyalty y, donde corresponda, antes del precio negociado; el importe definitivo se calcula al guardar la cotización.
- Si una ficha procede de la caché anterior, muestra «Consultar en línea» en lugar de un cálculo sin impuestos.

## Compatibilidad
No se alteran modelos, datos PostgreSQL, migraciones, permisos ni reglas de cálculo en los pedidos. Se reutilizan los campos de auditora por línea de las versiones anteriores. Los datos offline quedan intactos. El controlador y los assets deben actualizarse juntos.

## Instalación
1. Haga un respaldo y sincronice las operaciones pendientes, si es posible.
2. Sustituya solo la carpeta técnica `conedera_odoo_census_mobile`.
3. Reinicie todos los workers de Odoo; actualice el módulo a 18.0.1.5.15.
4. Abra `/catastro/app?version=18.0.1.5.15` y vuelva a consultar el catálogo en línea.
5. Compruebe casos de impuesto incluido, exento, posición fiscal, múltiples condiciones de pago y Loyalty en una base de pruebas.
