# v2.42 – Eliminar una evidencia de carga antes de aceptación del chofer

- Botón individual **Eliminar evidencia** en cada foto/video de carga de la ficha de ruta y del detalle de viaje (PWA).
- Incluye videos antiguos guardados en el campo `video_carga`.
- Solicita confirmación, CSRF y comprobación de rol, empresa, aceptación, estado, entrega y liquidaciones en servidor bajo bloqueo de filas.
- Si el viaje ya fue enviado pero no aceptado, vuelve automáticamente a Preparación.
- Borra únicamente el archivo solicitado y guarda una nota interna de auditoría en la ruta con usuario, ID, nombre, autor y fecha; no elimina guías ni otras evidencias.
- Si no quedan evidencias válidas, la ruta vuelve al estado Planificada y no puede enviarse hasta subir una nueva evidencia.
- Las fotos de entregas/cliente y firmas no se borran por esta acción.
- No se modifica `logistica_transcash`.
- Revisar en una copia de la base antes de instalar en producción; no hay servidor Odoo real en el entorno de pruebas.
