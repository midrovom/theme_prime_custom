# Actualización a 18.0.1.8.7

No desinstale el módulo. Haga backup de base y filestore. Reemplace completamente la carpeta del addon y ejecute:

```bash
sudo systemctl stop odoo18
sudo -u odoo18 /opt/odoo18/odoo18/odoo-bin \
  -c /etc/odoo18.conf -d NOMBRE_BASE \
  -u conedera_odoo_census --stop-after-init --no-http
sudo systemctl start odoo18
```

Después limpie/recargue los assets del navegador. Al entrar a **Catastro Comercial** debe abrirse directamente **Catastros** y el botón **Nuevo catastro** debe estar visible en la barra superior.
