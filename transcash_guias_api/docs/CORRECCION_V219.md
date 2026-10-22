# Corrección v2.19 — actualización de vistas PWA en Odoo 18

Error al actualizar desde v2.17 a v2.18:
`El elemento <xpath expr="//section[contains(@class,'tc-route-guide-filters')]/p"> no se puede localizar`.

## Causa
Al cargarse primero la vista padre `tc_pwa_filter_guides_v26`, Odoo revalida la vista hija previamente almacenada `tc_pwa_identity_fix_v27`. La versión anterior de esta vista hija todavía esperaba una sección `tc-route-guide-filters` que la v2.18 había eliminado. Además, otra vista nieta (`tc_pwa_driver_scope_v212`) aún esperaba la clase `tc-route-guide-breakdown` mientras se actualizaba la hija.

## Solución
* Se conserva un ancla QWeb no renderizada (`t-if="False"`) en `tc_pwa_filter_guides_v26` para que la vista hija antigua pueda validarse durante el upgrade.
* Se conserva una segunda ancla no renderizada en `tc_pwa_identity_fix_v27` para que la vista nieta antigua pueda validarse mientras Odoo actualiza las vistas en secuencia.
* Al finalizar la actualización, ningún bloque de diagnóstico ni listado antiguo se muestra en la PWA; quedan solo tres contadores dentro de las tarjetas de destino, chofer y transportista.

## Instalación
1. Respaldar base y addon.
2. Reemplazar `transcash_guias_api` por esta versión.
3. Reiniciar Odoo y actualizar exclusivamente `transcash_guias_api`.
4. Refrescar la PWA (limpiar caché de ser necesario).

Sin cambios en modelos operativos ni lógica de filtros o asignaciones.
