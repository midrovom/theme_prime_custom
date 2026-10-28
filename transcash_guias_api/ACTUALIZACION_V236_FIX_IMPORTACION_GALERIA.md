# v2.36 — Corrección de importación de la galería de evidencias

La v2.35 contiene un import absoluto de Python sin el espacio de nombres de Odoo en `controllers/route_trip_editing_v235.py`, que provoca `ModuleNotFoundError: No module named 'logistica_transcash'` al abrir el detalle del embarque.

Se sustituye por `from odoo.addons.logistica_transcash.controllers.evidence_hub import gallery_for_trip`, en concordancia con los controladores ya existentes. La galería, sus permisos, los botones de eliminación y asociación de rutas y el módulo base permanecen sin alteraciones.

## Instalación

Reemplazar solo el complemento `transcash_guias_api`, reiniciar Odoo y actualizar el módulo desde Aplicaciones. Probar el detalle de un embarque con y sin evidencias.

## Alcance de validación

Se validó sintaxis y empaquetado local; no se ha ejecutado Odoo ni PostgreSQL en este entorno.
