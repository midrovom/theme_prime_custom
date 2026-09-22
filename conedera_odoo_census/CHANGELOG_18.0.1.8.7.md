# Cambios 18.0.1.8.7

- La app Catastro Comercial abre directamente la lista/Kanban de Catastros.
- Botón **Nuevo catastro** permanente en las vistas Kanban y Lista.
- Se conserva el wizard existente de búsqueda por RUC/cédula o nombre antes de crear.
- Nueva tarjeta **Estado de solicitud de edición** dentro del Catastro protegido.
- Botón **Refrescar estado** que reabre exclusivamente la vista de Catastro.
- Se muestran estados Pendiente, Aprobada, Rechazada y Vencida, fechas y motivo solicitado.
- El rechazo ahora exige un motivo y el comercial puede verlo desde su Catastro.
- La lista de solicitudes ya no fuerza el filtro Pendientes, por lo que aprobadas/rechazadas quedan visibles.
- Enviar una solicitud reabre el Catastro para mostrar inmediatamente el estado Pendiente.
- Migración aditiva con Data Guard; no elimina datos existentes.
