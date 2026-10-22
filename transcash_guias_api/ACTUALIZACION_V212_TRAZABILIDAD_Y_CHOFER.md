# Transcash Guías API v2.12 — Trazabilidad y guías del chofer

## Alcance

- Únicamente se actualiza el addon `transcash_guias_api`.
- No se modifica `logistica_transcash`, API Administrator ni el flujo de confirmación de rutas.
- Guías para rutas y seguimiento: Kanban y lista muestran **todas** las guías visibles por permisos, incluidas las asignadas. Los filtros Disponibles, Con hoja de ruta y Con embarque ayudan a separar estados.
- Las guías muestran la hoja de ruta confirmada, su estado operativo y el embarque, con acceso directo al formulario de cada uno.
- Las hojas de ruta muestran botón **Guías del chofer**, consulta por usuario/contacto/cédula de su conductor y empresa actual, con proveedor y destino de cada guía; además, botón **Ver embarque** si ya existe.
- En la PWA, el resumen de otros choferes se sustituye por un diagnóstico exclusivo de las guías identificadas con el chofer de la ruta, incluso cuando ya tienen ruta/embarque o muestran una contradicción entre cédula y usuario.
- Las tablas de la PWA son de **solo lectura**; la selección existente sigue exigiendo guía libre, estado registrada y coincidencia de destino, chofer y proveedor.

## Instalación

1. Respaldar BD y addon.
2. Reemplazar carpeta `transcash_guias_api` por esta versión.
3. Reiniciar servidor Odoo y actualizar `transcash_guias_api` desde Apps.
4. Recargar interfaz/PWA para actualizar CSS.

## Pruebas recomendadas con datos de la empresa

1. Abrir **Guías para rutas y seguimiento**: las registradas sin ruta y las asignadas deben verse en la misma vista. Usar filtros para distinguir.
2. Desde una guía con `hoja_ruta_id`, pulsar **Abrir hoja de ruta**. Si esa ruta tiene `embarque_id`, pulsar **Ver embarque**.
3. Desde una hoja de ruta, pulsar **Guías del chofer**: confirmar que solo aparecen guías cuyo usuario, contacto o documento pertenecen al chofer, con proveedor/destino reales.
4. Entrar a la PWA con operador y abrir una ruta en borrador: revisar tabla Guías del chofer y sus combinaciones proveedor/destino. Guías asignadas o incompatibles deben figurar solo como consulta, nunca para marcar.
5. Cambiar a un chofer de otra identidad: no deben mostrarse guías ajenas.
6. Confirmar que **Seleccionar todas** solo marca candidatas elegibles; sin ampliar permisos.

### Limitaciones

- Las rutas aún en **borrador** conservan sus guías en `seleccion_guia_ids`. La relación `hoja_ruta_id` se llena al **confirmar** la ruta, por lo que antes de confirmar no existe una asignación operativa definitiva a nivel de guía.
- El diagnóstico del chofer en la PWA tiene límite de 201 candidatas y muestra como máximo 100 filas y 30 combinaciones en una consulta. Puede reducir los resultados mediante búsqueda por número de guía.
- Las coincidencias de identidad se basan en usuario, contacto o documento; nunca solo en nombres coincidentes. Los contactos duplicados con documento sin homologar todavía pueden requerir conciliación administrativa.
- El complemento no reescribe datos ni elimina registros duplicados durante la actualización.
