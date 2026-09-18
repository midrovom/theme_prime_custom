# Actualización a 18.0.1.8.1 — Odoo 18 Community

## Antes de actualizar

1. Haga backup de PostgreSQL y filestore.
2. No desinstale `conedera_odoo_census`.
3. Detenga el servicio Odoo.
4. Reemplace completamente la carpeta del addon por la versión 18.0.1.8.1.

## Comandos de referencia

```bash
sudo systemctl stop odoo18

rm -rf /opt/odoo18/odoo18/custom-addons/conedera_odoo_census

unzip conedera_odoo_census_18_community_18.0.1.8.1.zip \
  -d /opt/odoo18/odoo18/custom-addons/

grep version /opt/odoo18/odoo18/custom-addons/conedera_odoo_census/__manifest__.py
```

Debe mostrar `18.0.1.8.1`.

Ejecute el upgrade con el servicio web detenido:

```bash
sudo -u odoo18 /opt/odoo18/odoo18/odoo-bin \
  -c /etc/odoo18.conf \
  -d NOMBRE_DE_TU_BASE \
  -u conedera_odoo_census \
  --stop-after-init \
  --no-http
```

Si el comando termina sin traceback:

```bash
sudo systemctl start odoo18
```

Después haga recarga fuerte de assets en PC y vuelva a abrir Odoo en el móvil.

## Pruebas funcionales recomendadas

1. **RUC de otro vendedor**: desde Comercial A buscar un RUC catastrado por Comercial B. Debe mostrar que existe, no permitir crear, y ofrecer solicitud de reasignación.
2. **Aprobación**: el líder del equipo origen aprueba. La misma ficha debe quedar asignada al Comercial A sin cambiar el ID del cliente.
3. **Historia preservada**: comprobar visitas, fotos, bitácora, productos y proformas anteriores.
4. **Cotización histórica**: el nuevo comercial debe poder abrirla en lectura aunque la haya creado el vendedor anterior.
5. **Restricción**: antes de reasignar, Comercial A no debe poder abrir el Catastro ni sus contactos hijos.
6. **Supervisor**: debe ver los Catastros de los vendedores de su equipo, pero no debe poder cambiar el responsable/archivar/desactivar por edición directa.
7. **Vendedor**: no debe poder eliminar Catastros; en una ficha protegida debe solicitar habilitación para editar datos maestros.
8. **Concurrencia**: dos intentos de activar simultáneamente el mismo RUC deben terminar con un solo Catastro activo.

## Nota sobre duplicados históricos

La actualización no elimina duplicados antiguos automáticamente. Si ya existen dos Catastros activos con la misma identificación, el sistema los detecta y bloquea una reasignación hasta que un administrador defina cuál es la ficha canónica. Esto evita borrar historia sin una decisión humana.
