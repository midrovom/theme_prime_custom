# Recuperación de UndefinedColumn en Odoo 18

Si Odoo muestra `column res_partner.owner_contact_name does not exist`, el código nuevo ya está cargado pero el módulo aún no fue actualizado en la base.

1. Hacer backup de la base.
2. Detener el servicio Odoo.
3. Reemplazar completamente la carpeta del módulo por esta versión.
4. Ejecutar Odoo por CLI con `-d <DB> -u conedera_odoo_census --stop-after-init --no-http`.
5. Solo si el proceso termina sin ERROR/CRITICAL, iniciar nuevamente el servicio.

No crear columnas manualmente con ALTER TABLE. La pre-migración de esta versión prepara las columnas y el ORM completa la actualización.
