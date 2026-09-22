# Actualización a 18.0.1.8.3 — Odoo 18 Community

Esta versión corrige específicamente los dos errores vistos en móvil:

1. `Modelo gráfico sin definir para el equipo de ventas: Sitio web`.
2. `No puede acceder a los registros 'Visita comercial de ruta' (route.sale.visit)` al registrar/bloquear el Catastro.

## Antes de actualizar

1. Haga backup de la base de datos y del filestore.
2. **No desinstale** `conedera_odoo_census`.
3. Detenga el servicio Odoo.
4. Reemplace completamente la carpeta del módulo por 18.0.1.8.3.

Ejemplo:

```bash
sudo systemctl stop odoo18
cd /opt/odoo18/odoo18/custom-addons
rm -rf conedera_odoo_census
unzip /RUTA/conedera_odoo_census_18_community_18.0.1.8.3.zip \
  -d /opt/odoo18/odoo18/custom-addons/
```

Compruebe la versión:

```bash
grep version /opt/odoo18/odoo18/custom-addons/conedera_odoo_census/__manifest__.py
```

Debe mostrar `18.0.1.8.3`.

## Actualizar por consola

```bash
sudo -u odoo18 /opt/odoo18/odoo18/odoo-bin \
  -c /etc/odoo18.conf \
  -d NOMBRE_DE_TU_BASE \
  -u conedera_odoo_census \
  --stop-after-init \
  --no-http
```

No arranque Odoo si este comando termina con traceback.

Si termina correctamente:

```bash
sudo systemctl start odoo18
```

## Limpieza de caché móvil

Como cambian vistas y permisos, cierre completamente la pestaña de Odoo en el teléfono. Si continúa mostrando la vista anterior, borre los datos del sitio/caché del navegador o abra una pestaña privada para la primera prueba.

## Configuración después del upgrade

Entre con un Administrador de Catastro:

**Catastro Comercial > Configuración > Usuarios y permisos**

Seleccione usuario, rol y equipo. Para un Comercial el usuario se agrega al equipo; para Supervisor se configura como líder.

Luego revise:

**Catastro Comercial > Configuración > Equipos comerciales**

Esta pantalla es propia del módulo y ya no abre el dashboard gráfico estándar de Odoo.

## Pruebas mínimas

1. Abra un Catastro en borrador desde móvil.
2. En **Equipo comercial**, debe poder seleccionar únicamente equipos válidos donde el vendedor sea miembro/líder.
3. No debe aparecer `Sitio web` ni `Punto de Venta`.
4. Complete el Catastro y pulse **Registrar y proteger**.
5. La ficha debe volver a abrirse protegida, sin pedir acceso a `route.sale.visit`.
6. Intente cambiar el equipo después del bloqueo: debe impedirlo y dirigir al flujo de reasignación.
7. Confirme que visitas, proformas, fotos y bitácora anteriores siguen presentes.
