# Recuperación segura — Conedera Catastro 18.0.1.1.2

## Problema corregido
La base podía quedar con el código nuevo cargado pero sin todas las columnas de `res_partner`, provocando errores `UndefinedColumn` incluso al renderizar Website.

## Qué cambia
- La versión sube a `18.0.1.1.2`, asegurando que Odoo tenga una versión de migración superior a cualquier intento 18.0.1.1.1.
- La pre-migración 18.0.1.1.2 crea de forma idempotente **todas** las columnas persistentes del Catastro en `res_partner` y las dos columnas de `sale_order`.
- La propia pre-migración verifica que las columnas existan y aborta con un error claro si PostgreSQL no las creó.
- La post-migración vuelve a ejecutar, de forma idempotente, la conversión de datos legados y verifica las tablas relacionales nuevas.
- Se corrigió el test de GPS para que el cliente tenga una captura GPS verificada real.

## Actualización obligatoria por CLI
No actualizar desde Website ni desde Apps mientras el esquema esté inconsistente.

1. Detener Odoo.
2. Reemplazar completamente la carpeta del módulo por esta versión.
3. Ejecutar `-u conedera_odoo_census --stop-after-init --no-http`.
4. Solo iniciar el servicio web si el comando termina sin traceback.

Consulte el README incluido para los comandos y verificaciones.
