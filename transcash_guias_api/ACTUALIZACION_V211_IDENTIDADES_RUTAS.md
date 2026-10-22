# Actualización v2.11 — Guías que no aparecen en selección de PWA

**Módulo modificado:** `transcash_guias_api` únicamente. Mantener `logistica_transcash` sin cambios.

## Fallas verificadas en el código v2.10

1. La PWA compara `guia.destino_id.id == ruta.destino_id.id`, aunque el ERP haya creado una ficha `-NAJ`/`NAJ` y el catálogo de rutas use otra ficha con el **mismo código normalizado**.
2. Si las fichas `res.users` o `res.partner` fueron duplicadas, la PWA puede declarar diferencia por ID pese a que el RUC/cédula es igual. El módulo operativo, durante la confirmación, también compara IDs.
3. Cuando el usuario busca por número, faltaba un diagnóstico de la guía individual con el campo que realmente la bloquea.

## Solución v2.11

- Comparación de destino por la ficha o por código ERP exacto normalizado (por ejemplo `-NAJ` = `NAJ`), nunca por parecido de nombre.
- Chofer por el mismo usuario o por una identidad fiscal verificable cuando hay dos usuarios duplicados. No basta con tener el mismo nombre.
- Proveedor por la empresa comercial o su mismo RUC fiscal comprobado. No se admiten RUC diferentes.
- En **Agregar guías a la ruta**, introducir el número de la guía (por ejemplo `32802` o `TR-53968`) en **Buscar**. Aparecerá una tabla con la razón concreta de rechazo y los IDs de destino, chofer y transportista en guía versus ruta. No exige modificar el estado de la guía.
- Al guardar, si los tres criterios pasaron, unifica los vínculos técnicos de ESA guía con los de la ruta, sin modificar entidades maestras o viajes confirmados. Registro de auditoría en el chatter de la guía.
- Se conservan el filtro de compañía, estado Registrada, sin hoja de ruta/embarque y selección de máximo 100 guías.

## Prueba sugerida para las capturas

1. Buscar `32802` en la PWA de la ruta con chofer WILSON SEVICHAY, transportista LOGYTRACSA y destino Narcisa de Jesús.
2. Revisar si `Destino: guía / ruta` muestra `NAJ` con código `-NAJ` versus Narcisa de Jesús con código `NAJ`: ahora es una equivalencia segura.
3. Revisar el documento de identidad del usuario elegido y de la guía `0914936729`; si hay conflicto fiscal, la guía permanece bloqueada para revisión.
4. Revisar el RUC de `Proveedor a pagar` de la guía y el RUC del transportista de la ruta: si difieren, NO se autoriza la selección.
5. Seleccionar la guía, guardar, volver a abrir y confirmar la ruta solo después de verificar los tres vínculos.

## Límites

- Una captura solo muestra nombres, no prueba igualdad de RUC ni del ID de los usuarios.
- No hay conexión con la base PostgreSQL del servidor. La prueba final debe hacerse en Odoo.
- No fusiona ni elimina contactos o destinos históricos; limita la homologación a la guía seleccionada.
