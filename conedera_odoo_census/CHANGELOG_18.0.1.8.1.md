# Conedera Catastro Comercial — 18.0.1.8.1

## Objetivo

Revisión de endurecimiento de la 18.0.1.8.0. Esta versión no cambia el modelo funcional; refuerza unicidad global, seguridad de reasignaciones, visibilidad jerárquica y conservación de historial.

## Correcciones principales

- La unicidad RUC/cédula se serializa en PostgreSQL con `pg_advisory_xact_lock` antes de activar/crear un Catastro, cerrando el caso de dos vendedores intentando registrar simultáneamente la misma identificación.
- La identificación global reconoce RUC/cédula almacenado en un contacto hijo/dirección fiscal y lo asocia al `commercial_partner_id`.
- Al reutilizar una ficha antigua cuyo RUC estaba solo en un contacto hijo, el RUC se copia al cliente comercial principal.
- El autocomplete global sigue usando `sudo()` únicamente para existencia, pero no expone teléfono/email/dirección ni nombre real del responsable de Catastros ajenos.
- La selección recibida desde el navegador se revalida contra la búsqueda actual; un `partner_id` arbitrario no puede usarse para saltarse el flujo.
- Los contactos hijos de un Catastro heredan la restricción del cliente comercial: un vendedor ajeno no puede abrirlos para rodear la seguridad del Catastro.
- Un supervisor/líder de equipo no puede reasignar, archivar, desactivar, bloquear o desbloquear un Catastro por edición directa. Esos cambios pasan por flujos auditados; el Administrador de Ventas conserva capacidad administrativa.
- Las líneas de horario respetan el mismo bloqueo del maestro del Catastro en backend.
- Las solicitudes de edición programan actividad para el supervisor y la cierran al aprobar/rechazar.
- Las solicitudes de reasignación guardan origen/destino, validan que la asignación no haya cambiado antes de aprobar y cierran solicitudes competidoras después de una transferencia.
- Después de una reasignación, el nuevo responsable y el líder de su equipo pueden leer las proformas históricas y sus líneas, aunque las haya creado el vendedor anterior. Esta ampliación es solo de lectura.
- El Data Guard 1.8.1 comprueba catastros, visitas, horarios, relaciones de tipos/marcas, proformas originadas, solicitudes y adjuntos de fotos antes/después del upgrade. Si un conteo disminuye, aborta la actualización.

## Conservación de historial

Una reasignación nunca crea otro cliente ni mueve/elimina visitas o documentos. Cambia únicamente el responsable/equipo del mismo `res.partner`. Las visitas, fotos, proformas, productos cotizados y bitácora permanecen asociados a la ficha existente.
