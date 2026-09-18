# 18.0.1.7.0

- Búsqueda predictiva por RUC/cédula/nombre usando `res.partner` estándar.
- Selección explícita de ficha existente cuando hay duplicados visibles.
- Detección normalizada de RUC (ignora puntos, espacios y guiones).
- Solo un Catastro activo por RUC; contactos históricos duplicados no se eliminan.
- Nuevo rol Supervisor de Catastro reutilizando líder/miembros de `crm.team`.
- Seguridad por jerarquía: comercial propio / supervisor equipo / administrador todo.
- Nuevo campo de equipo comercial en el Catastro.
- Catastro en borrador hasta pulsar Registrar catastro; luego queda protegido.
- Solicitud persistente de habilitación de edición con motivo, aprobación/rechazo y vigencia de 2 horas.
- Cron horario para vencer habilitaciones.
- Protección backend de datos maestros, horarios, asignación, archivado y eliminación.
- Catastros existentes migrados a estado protegido sin borrar datos.
- Data Guard 18.0.1.7.0.

### Ajuste final de jerarquía
- El líder estándar del Equipo de Ventas (`crm.team.user_id`) actúa como supervisor automáticamente; ya no requiere asignar un segundo grupo para ver/aprobar su equipo.
- Los comerciales pueden consultar el estado de sus propias solicitudes de edición.
- La lista/kanban de Catastros muestra vendedor y equipo para facilitar supervisión.
