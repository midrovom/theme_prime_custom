# v2.28 — Destinos por código ERP

**Contrato:** `ruta.destino_codigo` del JSON alimenta `transcash.destino.codigo` y los campos `transcash.guia.destino` y `transcash.guia.destino_codigo`. `ruta.destino_ciudad` alimenta `transcash.destino.name`, `transcash.destino.ciudad` y `transcash.guia.destino_ciudad`. No utiliza nombre de destinatario ni dirección para generar códigos.

Se admiten `destino_codigo` y `destino_ciudad` tanto dentro de `ruta` como en la cabecera (compatibilidad). La ficha de destino se busca por código ERP normalizado y compañía, incluyendo fichas archivadas, y se actualiza su nombre/ciudad sin cambiar un código ya usado por rutas o tarifas. Si hay códigos antiguos equivalentes duplicados no se crea otro; quedan como error de catálogo para revisión. Las fichas inactivas no se reactivan automáticamente.

La PWA mantiene su filtro existente `transcash.guia.destino` contra `transcash.hoja.ruta.destino_id.codigo`. No se cambiaron choferes, transportistas, restricciones ni asignaciones operativas.

## Instalación

1. Respalda PostgreSQL y la carpeta del complemento.
2. Sustituye solo la carpeta `transcash_guias_api`, reinicia Odoo y actualiza el módulo.
3. En **Logística → Operación logística → Actualizar destinos ERP** ejecuta la reparación para las guías ya importadas; esta acción no vuelve a pedir datos a Symfony.
4. Ejecuta `getguiaslogistica` desde **API Administrator** para recibir códigos/ciudades nuevos. También se actualizarán catálogo y guías no asignadas.
5. Comprueba el catálogo **Maestro de destinos**, las tarjetas Kanban de guías y la búsqueda en PWA.

**Seguridad de la reparación:** No cambia destinos de guías que ya estén en ruta, embarcadas, entregadas o aprobadas. Solo rellena campos vacíos cuando el código coincide con la ruta existente. Si faltan códigos ERP se notifica y no se inventan.

Para revisar datos en PostgreSQL, consulta `docs/diagnostico_destinos_v228.sql` (solo lectura).
