# Actualización 18.0.1.8.5 — reparación de importación

Esta versión corrige/robustece el arranque del paquete. El inicializador correcto es:

```python
from . import models
```

El traceback recibido mostraba que el servidor estaba ejecutando un inicializador antiguo que intentaba importar `crm_team` desde la raíz. La 1.8.5 incluye además un bootstrap de compatibilidad, pero debe reemplazarse por completo la carpeta instalada.

## Ruta observada en el servidor

`/opt/odoo18/odoo18/custom-addons/theme_prime_custom/conedera_odoo_census`

## Procedimiento

1. Backup de base y filestore.
2. Detener Odoo.
3. Renombrar la carpeta actual como respaldo.
4. Descomprimir el ZIP nuevo exactamente en `.../theme_prime_custom/`.
5. Verificar `__init__.py`, `models/__init__.py` y versión.
6. Ejecutar `-u conedera_odoo_census --stop-after-init --no-http`.
7. Solo si termina limpio, arrancar Odoo.

No desinstalar el módulo.
