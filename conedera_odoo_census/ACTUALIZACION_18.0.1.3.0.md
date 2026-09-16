# Actualización a 18.0.1.3.0 — Odoo 18 Community

## Objetivo

Esta versión cambia el alta de clientes: no se crea un Catastro directamente. El vendedor debe usar **Catastro Comercial > Nuevo catastro**, ingresar RUC o nombre y validar primero si el cliente ya existe.

También incorpora CAPA como capacidad de compra obligatoria para operar y Marcas de celulares como dato opcional multiselección.

## Actualización recomendada

1. Haga backup de la base y filestore.
2. Detenga Odoo.
3. Reemplace por completo la carpeta `conedera_odoo_census`.
4. Ejecute el upgrade por CLI con HTTP detenido:

```bash
sudo -u odoo18 /opt/odoo18/odoo18/odoo-bin \
  -c /etc/odoo18.conf \
  -d NOMBRE_BASE \
  -u conedera_odoo_census \
  --stop-after-init \
  --no-http
```

5. Si termina sin traceback, inicie Odoo normalmente.

## Prueba funcional mínima

- Catastro Comercial > Nuevo catastro.
- Buscar un RUC existente: debe ofrecer **Abrir ficha existente** y no crear otra.
- Buscar un RUC nuevo: debe ofrecer **Crear nuevo catastro**.
- En el cliente, ingresar Número de tiendas y CAPA.
- Verificar que Marcas de celulares permita varias etiquetas.
- Dejar Marcas vacío: si el resto está completo, Visita/Proforma deben habilitarse.
- Poner CAPA en 0: Visita/Proforma deben quedar bloqueadas.
