# Catastro PWA 18.0.1.5.28 — Perfiles y comentario Radis

## Perfil Tienda prioritario

- Usuario con grupo `conedera_odoo_census_mobile.group_quote_retail`: interfaz **Ventas de Tienda**, aun con permisos previos de Catastro.
- No recibe padrón de catastros, visitas ni históricos de campo en `bootstrap`.
- No puede llamar a las operaciones de Catastro desde las rutas de la PWA (comprobación en servidor).
- Menú: Tienda, Cotizar, Pendientes, Más. Sin enlaces a `/web`, incluso en errores de arranque.
- Los pendientes antiguos de Catastro permanecen en IndexedDB, pero no se muestran ni se envían automáticamente en modo Tienda. Antes de cambiar de rol conviene sincronizarlos.
- No modifica el acceso directo a Odoo fuera de la aplicación ni sus ACL nativas.

## Comentario Radis **en este mismo módulo**

- Añadido `sale.order.catastro_pwa_origin` (Booleano almacenado, `copy=False`).
- Se marca `True` al crear una cotización PWA (incluido guardado/sync offline), duplicarla desde Tienda y editar un borrador desde PWA.
- `sale.order.extract_plain_text()` devuelve `client_order_ref` si `catastro_pwa_origin=True`.
- En cualquier cotización no marcada delega a `super().extract_plain_text()`, preservando `sale.order.note` del módulo Radis original.
- Envíos manuales y automáticos Radis que usen `extract_plain_text()` quedan cubiertos; no se modifica `stock_api_assing` ni el JSON de porcentajes/código ERP.
- Si la PWA no proporciona referencia, comentario queda vacío para la cotización marcada.
- Cotizaciones anteriores a esta versión no se clasifican por inferencia. Si se editan y guardan desde la PWA, quedan marcadas; si no, mantienen el comportamiento anterior.
- Si ya instaló el antiguo módulo opcional `catastro_pwa_radis_comment_bridge`, no lo mantenga como dependencia necesaria: revise su retirada en una base de prueba después de actualizar, para evitar dos implementaciones del mismo método.

## Actualización

1. Respalde base de datos, filestore, addons y operaciones pendientes.
2. Reemplace **solo** `conedera_odoo_census_mobile`, conserve los demás módulos.
3. Reinicie los workers de Odoo y actualice el módulo a `18.0.1.5.28` desde Aplicaciones.
4. Abra `/catastro/app?version=18.0.1.5.28`, confirme la versión de servidor y de interfaz.
5. Pruebe una cotización nueva desde Tienda, otra desde Campo y una desde el backend. Confirme el JSON de Radis: para PWA debe igualar `client_order_ref`; para backend debe seguir usando el comentario de `note`.
6. No borre IndexedDB; las colas antiguas se preservan.

**No probado contra tu servidor/PostgreSQL real.** No se debe dar por validado en producción sin ensayar la instalación y el comportamiento de Radis.
