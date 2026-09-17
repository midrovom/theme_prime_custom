# Actualización 18.0.1.6.0 — Visita móvil y fotografía visible

Esta versión no elimina ni renombra campos de negocio. Es una actualización de interfaz y comportamiento.

## Cambios
- La fotografía capturada se vuelve a cargar desde Odoo después de guardar/reabrir la visita.
- La foto se muestra grande y se puede ampliar a pantalla completa tocándola/clicándola.
- Se agrega respaldo "Ver foto en una ventana".
- En móvil aparecen acciones grandes y fijas: "Guardar visita" y "Finalizar visita".
- El botón Guardar fuerza el guardado del formulario y confirma al usuario.
- Finalizar conserva los datos recién editados porque Odoo guarda el formulario antes de ejecutar el botón de objeto.
- La tarjeta kanban de visitas muestra la evidencia fotográfica cuando existe.
- Se conserva el Data Guard antes/después del upgrade.

## Actualización
Detenga Odoo, reemplace completamente la carpeta del módulo y ejecute:

```bash
sudo -u odoo18 /opt/odoo18/odoo18/odoo-bin \
  -c /etc/odoo18.conf \
  -d NOMBRE_BASE \
  -u conedera_odoo_census \
  --stop-after-init --no-http
```

No desinstale el módulo.
