# Transcash Guías API v2.27 — reparación del registro Odoo 18

## Causa

El modelo `transcash.embarque.estado_financiero` está definido por `logistica_transcash` como campo `Selection` calculado **sin** valor `default`. En v2.26, la extensión añadía la opción `no_aplica` con política `ondelete={"no_aplica": "set default"}`. Odoo 18 rechaza esta definición durante la construcción del registro de modelos.

## Corrección

`models/transport_client_mode.py` cambia exclusivamente la política `ondelete` de la opción `no_aplica` de `estado_financiero` a `set null`. Mantiene la función `_compute_estado_financiero`, el valor `no_aplica` cuando la modalidad es `cliente` y todas las protecciones contra liquidación. No se agregan ni eliminan columnas; no hay migración de datos. La definición de `estado_aprobacion` se conserva porque su campo base sí tiene `default='pendiente'`.

## Instalación de recuperación

1. Detener Odoo y respaldar la carpeta actual del complemento y PostgreSQL.
2. Reemplazar `transcash_guias_api` con el contenido de este paquete.
3. Reiniciar Odoo.
4. Actualizar **solo** `transcash_guias_api` en Aplicaciones (la actualización anterior abortada normalmente hizo rollback).
5. Verificar embarque normal y modalidad `cliente` en una base de pruebas antes de producción.

No modificar `logistica_transcash`. Si el reinicio continúa fallando, adjuntar el **primer error completo** nuevo del log; no cambiar manualmente la base de datos.
