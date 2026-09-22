# Actualización a 18.0.1.8.6

Esta versión corrige exclusivamente presentación/UX del Catastro y añade un resumen calculado del horario. No desinstale el módulo.

1. Realice backup de base de datos y filestore.
2. Detenga Odoo.
3. Reemplace completamente la carpeta `conedera_odoo_census` por la 18.0.1.8.6.
4. Ejecute `-u conedera_odoo_census --stop-after-init --no-http`.
5. Inicie Odoo y haga recarga fuerte de assets en navegador/móvil.

## Verificación
- En la ficha móvil debe aparecer **una sola** `Empresa del Catastro`.
- Un horario guardado como Lunes 09:00–18:00 debe seguir visible después de guardar/proteger y al volver a abrir la ficha.
- El contador One2many deja de ser la presentación principal del horario en modo protegido.
