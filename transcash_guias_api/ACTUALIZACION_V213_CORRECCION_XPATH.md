# Transcash Guías API 18.0.2.13.0 — Corrección de actualización XML

## Problema resuelto

Al actualizar la versión 2.12, Odoo 18 rechazaba la vista heredada
`view_tc_guia_search_trazabilidad_v212` con el mensaje:

`View inheritance may not use attribute 'string' as a selector.`

## Cambios

Se corrigieron los tres selectores de `views/route_traceability_views.xml`
que dependían del atributo traducible `string`:

- `//group[@string='Agrupar por']` → `//search/group[filter[@name='por_estado']]`
- `//group[@string='Guía y ruta']/field[@name='hoja_ruta_id']` → `//group[field[@name='external_id_erp']]/field[@name='hoja_ruta_id']`
- `//page[@string='Guías de la ruta']/group[1]` → `//page[field[@name='seleccion_guia_ids']]/group[1]`

No se modifican datos, modelos, reglas de selección de guías, ni asignaciones.

## Comprobaciones locales

- Los selectores modificados tienen exactamente una coincidencia en las vistas
  padre `logistica_transcash` v5.32 proporcionadas para el proyecto.
- Los selectores de los dos kanban heredados también tienen coincidencias.
- Parseo de todos los XML del complemento y compilación de Python sin errores.

Estas comprobaciones no equivalen a instalar el módulo en una base real Odoo.

## Instalación

1. Respaldar base de datos y addons.
2. Reemplazar la carpeta `transcash_guias_api` por la de este paquete.
3. Reiniciar el servicio Odoo.
4. Actualizar `transcash_guias_api` en Aplicaciones o con `-u transcash_guias_api`.
5. Verificar el panel «Guías para rutas y seguimiento», hoja de ruta y
   botón «Guías del chofer».

Si aparece otro error de vista, facilitar el siguiente traceback completo.
