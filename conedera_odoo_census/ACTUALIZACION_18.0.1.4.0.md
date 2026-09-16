# Actualización a 18.0.1.4.0

1. Backup de PostgreSQL.
2. Detener Odoo.
3. Reemplazar completamente `custom-addons/conedera_odoo_census` por esta versión.
4. Ejecutar el upgrade por CLI con HTTP desactivado:

```bash
sudo -u odoo18 /opt/odoo18/odoo18/odoo-bin \
  -c /etc/odoo18.conf \
  -d NOMBRE_BASE \
  -u conedera_odoo_census \
  --stop-after-init \
  --no-http
```

5. El proceso debe crear/verificar estas vistas PostgreSQL:
   - `conedera_census_commercial_timeline`
   - `conedera_census_product_quote_summary`
   - `conedera_census_product_quote_line`
6. Iniciar Odoo y recargar los assets del navegador.

## Pruebas funcionales mínimas
- Buscar un RUC/cédula existente con guiones/espacios diferentes y comprobar que reutiliza el contacto.
- Registrar una visita y comprobar que aparece como tarjeta en Bitácora móvil.
- Crear una proforma con al menos dos productos y comprobar que aparece en la Bitácora.
- Comprobar el resumen por producto y que el historial abre las líneas ordenadas por fecha descendente.
- Abrir un producto estándar y comprobar las métricas de proformas y el botón de historial.
