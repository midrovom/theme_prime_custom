# Validación estática — Conedera Catastro 18.0.1.7.0

Resultado: **PASSED**.

Validaciones ejecutadas sobre el paquete final:

- 31 archivos Python compilan sin errores de sintaxis.
- 16 XML parsean correctamente.
- 103 IDs XML explícitos son únicos.
- Manifest válido, versión `18.0.1.7.0`, dependencias Community y rutas de data/assets existentes.
- 19 ACL apuntan a modelos declarados.
- 45 botones `type="object"` resuelven a métodos Python existentes.
- Todos los `domain_force` del XML de seguridad tienen sintaxis válida.
- JavaScript de GPS y cámara pasa `node --check`.
- Alta predictiva por RUC/cédula/nombre presente y reutiliza `res.partner`.
- Flujo de duplicados exige selección y evita activar un segundo Catastro canónico con el mismo documento.
- Jerarquía dinámica: comercial ve propio; líder estándar del Equipo de Ventas ve su equipo; Administrador de Ventas ve todo.
- Catastro registrado queda protegido en UI y backend.
- Comercial no puede borrar/desactivar el Catastro; el formulario dedicado oculta Eliminar/Duplicar.
- Solicitud de edición persistente con motivo, aprobación/rechazo y habilitación temporal de 2 horas.
- El líder del Equipo de Ventas actúa como supervisor automáticamente; no requiere grupo adicional.
- Cron horario vence habilitaciones temporales.
- Migración 1.7 repara las nuevas columnas de control y recupera `user_id` desde `census_user_id` cuando un Catastro histórico no tenía vendedor asignado.
- Los Catastros históricos se bloquean tras la actualización.
- Data Guard compara conteos pre/post y aborta si disminuyen.
- No se detectan `DELETE FROM`, `TRUNCATE`, `DROP TABLE` ni `DROP COLUMN` en las migraciones del módulo.

## Límite de esta validación

Este entorno no contiene un runtime completo de Odoo 18 + PostgreSQL, por lo que no se ejecutó un `-u` real ni pruebas HTTP/OWL contra una base Odoo. La validación definitiva de instalación es el upgrade CLI en la base de pruebas/producción del servidor del usuario.
