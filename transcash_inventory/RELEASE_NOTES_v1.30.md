# Inventario Inteligente v1.30 — corrección de actualización Odoo 18

**Causa confirmada:** durante `button_immediate_upgrade`, Odoo lee los campos
almacenados de `res.company` antes de crear la nueva columna
`transcash_photo_site_url`, lo cual provoca `psycopg2.errors.UndefinedColumn`.

**Solución:** se conserva el menú y campo visible, pero
`res.company.transcash_photo_site_url` ahora es un campo calculado NO almacenado
con inversa. La URL se guarda en `ir.config_parameter` con una clave distinta
por empresa (`transcash_inventory.photo_site_url.company_<id>`). Ya no hace
falta añadir ni modificar columnas de `res_company`.

Si otra instancia consiguió instalar v1.29 y tiene valores en la columna antigua,
se leen como fallback hasta el siguiente guardado del formulario. No se
borran columnas ni datos durante esta actualización.

**Actualización:** respaldo PostgreSQL + filestore; sustituya la carpeta
`transcash_inventory` completa; reinicie TODOS los procesos Odoo; actualice
el módulo desde Aplicaciones. Verifique el menú Configuración de fotografías
en la empresa activa y pruebe una consulta de fotografías.

**Validación disponible:** sintaxis y XML, comprobación de campo `store=False`,
pruebas aisladas con dos empresas y URL distinta. **Pendiente:** actualización
real en el servidor Odoo 18 del usuario.
