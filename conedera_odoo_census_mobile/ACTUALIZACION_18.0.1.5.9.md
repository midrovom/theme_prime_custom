# Catastro PWA 18.0.1.5.9 — reparación de actualización Odoo 18

## Error que corrige

```text
psycopg2.errors.UndefinedColumn: column res_company.catastro_retail_partner_id does not exist
```

Durante `ir.module.module.button_immediate_upgrade`, Odoo puede instalar/actualizar dependencias antes de inicializar las nuevas columnas. El ORM precarga las columnas almacenadas de `res.company` al consultar el país y el contacto de las compañías, y tropieza con el campo agregado por la versión 18.0.1.5.8.

La versión 18.0.1.5.9 convierte `res.company.catastro_retail_partner_id` en un campo **calculado no almacenado** que lee/escribe el cliente de Consumidor Final en `ir.config_parameter`, con una clave independiente por `res.company.id`. El formulario administrativo y las funciones de la PWA conservan el mismo campo lógico; **ya no hace falta crear una columna nueva en `res_company`**. Si una instalación anterior llegó a guardar datos en esa columna, el valor se puede leer automáticamente como alternativa hasta que el administrador guarde el valor configurado, sin acceder a la columna si no existe.

El módulo puente `catastro_pwa_loyalty_bridge` pasa a 18.0.1.0.1, con `auto_install=False` para impedir instalaciones automáticas inesperadas durante la actualización del principal. Si se necesitan promociones y recargos conjuntos debe instalarse explícitamente, después del módulo principal y con `sale_loyalty` disponible.

## Procedimiento recomendado

1. Hacer una copia de seguridad de PostgreSQL y de `addons_path`. **No desinstalar** `conedera_odoo_census`, el módulo PWA ni borrar los datos del navegador.
2. Detener todas las instancias/trabajadores de Odoo que utilicen la base de datos para no mezclar código anterior y corregido.
3. Sustituir la carpeta `conedera_odoo_census_mobile` por la del ZIP 18.0.1.5.9, sin cambiar su nombre técnico. Si se usa el puente Loyalty, sustituir también `catastro_pwa_loyalty_bridge` por 18.0.1.0.1.
4. Reiniciar el servidor Odoo y actualizar **primero** `conedera_odoo_census_mobile`. No activar instalaciones adicionales de módulos con dependencias pendientes durante esta prueba.
5. Una vez que la actualización principal termine sin errores, instalar/actualizar manualmente `catastro_pwa_loyalty_bridge` si procede y si `sale_loyalty` ya está instalado.
6. Abrir `/catastro/app?version=18.0.1.5.9`; comprobar Catastro, Cotizador de tienda, listas de precios, stock y las condiciones de pago.
7. En **Catastro > Configuración > Consumidor final por empresa**, comprobar que el cliente está seleccionado en cada empresa. Si aún no estaba definido, establecerlo.

## Comprobaciones y límites

- El cambio no escribe manualmente en el esquema de PostgreSQL ni borra configuraciones antiguas.
- Los archivos JavaScript/Service Worker cambian solo en su identificador de versión/caché, para evitar desajustes de recursos tras actualizar. IndexedDB no se modifica.
- Se mantiene `negotiable_price` como campo personalizado existente de `sale.order.line`.
- Se conserva la ruta `/catastro/app`, el proceso de stock por bodega, los grupos de Tienda y Negociador y las reglas de Loyalty/recargos.
- Los archivos fueron sometidos a comprobaciones estáticas y pruebas de lógica aisladas; **no es una validación de instalación en tu servidor PostgreSQL**. Instalar primero en una copia de pruebas.

Si se produce un nuevo error con una columna distinta, recoger la primera línea `UndefinedColumn` del registro: podría corresponder a otro módulo personalizado o a otro campo nuevo que también deba migrarse de forma segura.
