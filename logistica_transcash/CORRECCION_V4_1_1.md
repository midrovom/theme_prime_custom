# Transcash V4.1.1 — Corrección del error en Mis guías

## Error corregido

Al abrir `/transcash/guias`, el template `logistica_transcash.portal_guias` fallaba con:

```
TypeError: 'type' object is not subscriptable
```

En el bucle de filtros de estado se usaba `t-as="filter"`, que colisionaba con el tipo incorporado de Python. Ahora se usa `t-as="filtro_guia"` y sus referencias `filtro_guia[0]` y `filtro_guia[1]`.

## Aplicación de la corrección en VPS

1. Respalde la base de datos y los archivos del módulo.
2. Detenga Odoo o prepare una ventana controlada para actualizarlo.
3. Sustituya la carpeta **logistica_transcash** que existe en su `addons_path` por la nueva carpeta de este ZIP. Mantenga el mismo nombre de módulo.
4. Reinicie el servicio Odoo (nombre según su instalación).
5. En Odoo, con modo desarrollador: Aplicaciones → Actualizar lista de aplicaciones → buscar `Transcash - Seguimiento de Guias` → Actualizar.
6. Abra `/transcash/guias` desde una sesión autenticada de usuario chofer que tenga guía asignada.
7. Verifique que los filtros Todas, Embarque, En ruta y En destino funcionen.

**IMPORTANTE**: Copiar XML al VPS no actualiza automáticamente los templates guardados en la base de datos; es imprescindible **Actualizar** el módulo o ejecutar `odoo -d NOMBRE_BD -u logistica_transcash --stop-after-init` con los parámetros concretos del servicio.

Si persiste el error después de actualizar, reinicie los procesos workers de Odoo, borre la caché de navegador (o pruebe ventana privada) y revise el log: `journalctl -u NOMBRE_SERVICIO -n 150 --no-pager`.

No desinstale el módulo: una desinstalación podría afectar sus registros.

Esta corrección supera validaciones estáticas, pero no ha sido ejecutada en una instancia real de Odoo.
