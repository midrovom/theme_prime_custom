# Transcash Guías API 2.6: PWA, filtros obligatorios

- Solo se modifica `transcash_guias_api`, no `logistica_transcash`.
- La página `/transcash/operacion/rutas/<id>` mantiene el transportista, chofer y destino seleccionados al crear la hoja de ruta y limita el listado a guías con coincidencia exacta de los tres parámetros.
- El transportista se compara por empresa comercial de `res.partner`; el chofer, por `res.users` asignado; y el destino mediante la validación existente del maestro.
- No se admiten guías sin usuario de chofer ni sin transportista relacionado. Deben conciliarse primero.
- `Seleccionar todas` marca hasta 100 guías elegibles visibles del resultado; si hay más, use la búsqueda por guía para otra ruta/embarque. No se seleccionan guías fuera de los tres filtros.
- Se vuelve a comprobar todo al guardar desde el servidor: incluso si un POST contiene IDs alterados, la asignación se rechaza.
- Las guías previamente seleccionadas que ahora son incompatibles se muestran deshabilitadas para que puedan retirarse al guardar.
- El portal de operaciones es exclusivamente para operador/jefe logístico según las reglas originales.
- **No habilita acceso Portal ni reasigna choferes durante la sincronización**.

Instalación: hacer respaldo, sustituir carpeta `transcash_guias_api`, reiniciar Odoo 18, actualizar módulo en Aplicaciones, recargar PWA (Ctrl+F5), comprobar selección sobre ruta borrador y pruebas de rechazo de POST alterado.
