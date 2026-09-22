# Reparación de importación — 18.0.1.8.5

El traceback recibido muestra que Odoo carga:

`/opt/odoo18/odoo18/custom-addons/theme_prime_custom/conedera_odoo_census/__init__.py`

con una importación raíz `from . import crm_team`. La estructura canónica del addon es:

- `conedera_odoo_census/__init__.py` → `from . import models`
- `conedera_odoo_census/models/__init__.py` → importa `crm_team`, `res_partner`, etc.
- `conedera_odoo_census/models/crm_team.py` → extensión de `crm.team`

La 18.0.1.8.5 incluye además un bootstrap raíz `crm_team.py` para tolerar temporalmente un inicializador antiguo/aplanado, pero debe reemplazarse la carpeta completa.

## Comprobación previa

```bash
cd /opt/odoo18/odoo18/custom-addons/theme_prime_custom/conedera_odoo_census
printf '%s\n' '--- ROOT INIT ---'
cat __init__.py
printf '%s\n' '--- MODELS INIT ---'
head -30 models/__init__.py
```

El ROOT INIT correcto debe ser exactamente:

```python
from . import models
```

## Reemplazo limpio

```bash
sudo systemctl stop odoo18
cd /opt/odoo18/odoo18/custom-addons/theme_prime_custom
sudo mv conedera_odoo_census conedera_odoo_census.bak_$(date +%Y%m%d_%H%M%S)
sudo unzip /RUTA/conedera_odoo_census_18_community_18.0.1.8.5.zip -d .
```

Verificar:

```bash
cat conedera_odoo_census/__init__.py
head -30 conedera_odoo_census/models/__init__.py
grep version conedera_odoo_census/__manifest__.py
find conedera_odoo_census -maxdepth 1 -type f -printf '%f\n' | sort
```

Debe existir `__init__.py` y NO debe existir un archivo mal escrito `_init_.py`.

## Upgrade

```bash
sudo -u odoo18 /opt/odoo18/odoo18/odoo-bin \
  -c /etc/odoo18.conf \
  -d NOMBRE_DE_TU_BASE \
  -u conedera_odoo_census \
  --stop-after-init \
  --no-http
```

Solo si el comando termina sin traceback:

```bash
sudo systemctl start odoo18
```

No desinstalar el módulo.
