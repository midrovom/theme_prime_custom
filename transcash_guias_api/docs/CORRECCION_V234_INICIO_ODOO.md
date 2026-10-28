# v2.34 — Corrección de bloqueo de arranque

## Error

`TypeError: __bases__ assignment: 'PwaGuiaAuditNote' object layout differs from 'Guia'`

La v2.33 usaba `_PwaAuditNoteMixin` (clase Python sin herencia ORM) como
primera base de tres extensiones de modelos `transcash.hoja.ruta`,
`transcash.embarque` y `transcash.guia`. Odoo 18 intenta reconstruir sus
bases al crear el registro y falla.

## Cambio

Las tres clases ahora heredan exclusivamente de `models.Model`; una función
ordinaria `_pwa_message_post` comparte la lógica de auditoría. El comportamiento
selectivo de notas internas se mantiene sin afectar mensajes explícitos.

## Recuperación

Con Odoo detenido, reemplazar la carpeta `transcash_guias_api` por la incluida
en este ZIP; reiniciar Odoo; actualizar el módulo. No requiere intervención
en PostgreSQL ni actualización de `logistica_transcash`.

## Verificación

Probar inicio del registro de Odoo, abrir un embarque y registrar una evidencia
con un usuario sin correo electrónico, luego probar notificaciones explícitas.
La revisión local de archivos no sustituye una prueba en el servidor real.
