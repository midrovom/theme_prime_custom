# Actualización 18.0.1.2.1 — Odoo 18 Community

## Objetivo

Esta versión hace obligatorio completar el catastro antes de operar comercialmente desde él. El GPS es la única excepción temporal mientras el servidor se utilice sin HTTPS.

## Reglas

Se puede guardar un catastro incompleto. Sin embargo, `Registrar visita` y `Crear proforma` solo se habilitan cuando están completos:

- Razón social / cliente
- RUC
- Nombre comercial / local
- Número de tiendas / locales mayor a cero
- Uno o varios tipos de negocio
- Canal comercial
- Nombre y teléfono del dueño
- Contacto comercial
- Teléfono o móvil del contacto
- Email
- Dirección
- Ciudad
- Al menos una franja de horario

GPS no forma parte de esta validación temporalmente.

## Actualización recomendada

Con Odoo detenido, sustituya completamente la carpeta del módulo y ejecute:

```bash
sudo -u odoo18 /opt/odoo18/odoo18/odoo-bin \
  -c /etc/odoo18.conf \
  -d NOMBRE_DE_TU_BASE \
  -u conedera_odoo_census \
  --stop-after-init \
  --no-http
```

Luego inicie el servicio normalmente.
