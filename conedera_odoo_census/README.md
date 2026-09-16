# Conedera Catastro Comercial — Odoo 18 Community

Versión: **18.0.1.1.2**

Módulo Community para catastro móvil de clientes, múltiples tipos de negocio, horarios estructurados, visitas con GPS y generación de proformas estándar de Odoo.

## Recuperación de una base con `UndefinedColumn`

Si la base muestra errores como `res_partner.owner_contact_name does not exist`, **no use la interfaz web para actualizar**. El código ya se cargó pero la base no terminó el upgrade.

Ejemplo (ajuste usuario, configuración y base):

```bash
sudo systemctl stop odoo18
cd /opt/odoo18/odoo18/custom-addons
sudo rm -rf conedera_odoo_census
sudo unzip /RUTA/conedera_odoo_census_18_community_18.0.1.1.2.zip -d /opt/odoo18/odoo18/custom-addons/

sudo -u odoo18 /opt/odoo18/odoo18/odoo-bin \
  -c /etc/odoo18.conf \
  -d NOMBRE_BASE \
  -u conedera_odoo_census \
  --stop-after-init \
  --no-http
```

Solo si ese comando termina limpio:

```bash
sudo systemctl start odoo18
```

## Verificación SQL posterior

```sql
SELECT column_name
FROM information_schema.columns
WHERE table_name = 'res_partner'
  AND column_name IN (
    'census_active','census_date','census_user_id','commercial_name','store_count',
    'owner_contact_name','owner_phone','commercial_contact_name','commercial_contact_phone',
    'business_description','customer_segment','business_type','customer_census_type','capa',
    'census_gps_payload','census_gps_accuracy','census_gps_captured_at'
  )
ORDER BY column_name;
```

Deben aparecer **17 columnas**.
