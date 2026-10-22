# v2.17 - PWA: resumen del chofer

En la pantalla de selección de guías de una hoja de ruta, la sección **Guías del chofer seleccionado** muestra exclusivamente:

- **Total de guías del chofer**: valor calculado por la consulta existente del chofer.
- **Combinaciones transporte/destino**: cantidad de grupos devueltos por el resumen existente.

Se eliminaron las dos tablas de detalle y los avisos secundarios de esa sección. No se modificaron la selección de guías, los filtros de chofer/proveedor/destino ni los controles de seguridad.

Actualización: sustituir `transcash_guias_api`, reiniciar Odoo, actualizar la aplicación y recargar la PWA.

**Nota:** en versiones actuales el servicio acota la consulta diagnóstica a 201 guías y el resumen de combinaciones a 30 grupos. Si un chofer supera esos límites, los indicadores pueden mostrar solo el subconjunto consultado. Esta entrega es deliberadamente una mejora de presentación, sin cambiar la lógica de conteo existente.
