# Actualización a 18.0.1.8.2 — Odoo 18 Community

## Antes de actualizar

1. Realice backup de PostgreSQL y del filestore.
2. **No desinstale** `conedera_odoo_census`.
3. Detenga el servicio Odoo.
4. Reemplace completamente la carpeta del módulo por la versión 18.0.1.8.2.

Ejemplo:

```bash
sudo systemctl stop odoo18

cd /opt/odoo18/odoo18/custom-addons
rm -rf conedera_odoo_census
unzip /RUTA/conedera_odoo_census_18_community_18.0.1.8.2.zip \
  -d /opt/odoo18/odoo18/custom-addons/

grep version /opt/odoo18/odoo18/custom-addons/conedera_odoo_census/__manifest__.py
```

Debe mostrar `18.0.1.8.2`.

## Actualizar la base

Ejecute el upgrade por CLI con HTTP detenido:

```bash
sudo -u odoo18 /opt/odoo18/odoo18/odoo-bin \
  -c /etc/odoo18.conf \
  -d NOMBRE_DE_TU_BASE \
  -u conedera_odoo_census \
  --stop-after-init \
  --no-http
```

No inicie el servicio normal si este comando termina con traceback.

Si termina correctamente:

```bash
sudo systemctl start odoo18
```

Luego haga recarga fuerte del navegador / cierre y vuelva a abrir Odoo en el teléfono.

## Configurar permisos

Entre con un Administrador de Catastro:

**Catastro Comercial > Configuración > Usuarios y permisos**

Asigne uno de estos roles:

- Comercial
- Supervisor
- Administrador

El asistente modifica únicamente los grupos del Catastro; no altera otros permisos de Odoo.

## Configurar equipos

Entre a:

**Catastro Comercial > Configuración > Equipos comerciales**

Para cada equipo:

- configure **Líder del equipo**;
- agregue los vendedores como **Miembros**;
- active **Disponible para Catastro**.

`Sitio web` y `Punto de Venta` son equipos técnicos de Odoo y el módulo no permite habilitarlos para Catastro.

El campo Equipo comercial de la ficha del cliente es de solo lectura: se determina automáticamente desde el vendedor responsable.

## Prueba mínima después del upgrade

1. Abra `Usuarios y permisos` y verifique su rol.
2. Abra `Equipos comerciales` y confirme líder, miembros y `Disponible para Catastro`.
3. Abra un Catastro propio incompleto, termine los datos y pulse **Registrar y proteger**.
4. Debe registrarse sin error de acceso y quedar protegido.
5. Como Comercial, confirme que no puede eliminar el Catastro.
6. Como Supervisor, confirme que ve Catastros de un equipo que lidera.
7. En móvil, confirme que al abrir la ficha no aparece el error de modelo gráfico del equipo `Sitio web`.
