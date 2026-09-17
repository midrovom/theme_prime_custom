# Actualización a 18.0.1.5.0 — Odoo 18 Community

## Objetivo
Esta versión corrige visibilidad de bitácora/productos, protege datos durante upgrades y mejora la experiencia móvil/cámara.

## Muy importante
No desinstale el módulo. Una actualización (`-u`) conserva tablas y registros; una desinstalación sí puede eliminar datos propios del módulo.

1. Haga respaldo de PostgreSQL y filestore.
2. Detenga Odoo.
3. Reemplace completamente la carpeta `conedera_odoo_census` por la versión 18.0.1.5.0.
4. Ejecute el upgrade por CLI con `--stop-after-init --no-http`.
5. Solo arranque el servicio web si el upgrade termina sin traceback.

Ejemplo:

```bash
sudo systemctl stop odoo18
rm -rf /opt/odoo18/odoo18/custom-addons/conedera_odoo_census
unzip conedera_odoo_census_18_community_18.0.1.5.0.zip -d /opt/odoo18/odoo18/custom-addons/

sudo -u odoo18 /opt/odoo18/odoo18/odoo-bin \
  -c /etc/odoo18.conf \
  -d NOMBRE_BASE \
  -u conedera_odoo_census \
  --stop-after-init \
  --no-http

sudo systemctl start odoo18
```

## Protección de datos
La migración 18.0.1.5.0 registra conteos antes y después para:
- clientes catastrados;
- visitas;
- horarios;
- relaciones de tipos de negocio;
- relaciones de marcas;
- proformas creadas desde Catastro.

Si después del upgrade cualquiera de esos conteos disminuye, la migración lanza error y la transacción se revierte.

## Pruebas posteriores
1. Abrir un catastro con visitas antiguas: deben aparecer en Bitácora.
2. Abrir un cliente con cotizaciones realizadas a una dirección/contacto hijo: sus productos deben aparecer en Productos cotizados.
3. Abrir un producto cotizado: debe mostrar cantidad, importe, promedio y botón Proformas.
4. Desde móvil crear visita y pulsar Tomar foto: debe abrir la cámara y guardar la imagen al guardar la visita.
5. Buscar por RUC guardado en un contacto hijo: debe abrir el cliente comercial principal, no crear un duplicado.
